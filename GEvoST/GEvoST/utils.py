import os
import oss2
import io
import matplotlib.pyplot as plt
import random
import numpy as np
import pandas as pd
import torch
import dgl
import scanpy as sc
from anndata import AnnData
from tqdm import tqdm
from sklearn.decomposition import PCA
from scipy.sparse import issparse
from torch.utils.data import Dataset, DataLoader
from sklearn.neighbors import NearestNeighbors
from typing import Optional, Union
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from sklearn.preprocessing import LabelEncoder

def labels_from_obs(adata, key, *, drop_na=True, fill_na_token="__UNK__"):
    """
    把 adata.obs[key] 转成 (long) 整数标签，并返回映射表。
    - drop_na=True: 丢弃缺失项（更稳，适合 triplet）；False 时会把缺失项编码为一个特殊类
    """
    s = adata.obs[key].copy()

    # 1) 统一成字符串/分类，处理缺失
    if drop_na:
        mask = ~s.isna()
        s = s[mask]
        index_keep = s.index.values
    else:
        s = s.astype("string").fillna(fill_na_token)
        index_keep = adata.obs_names.values

    # 2) 确定性编码成 0..C-1
    le = LabelEncoder()
    y = le.fit_transform(s.values)  # ndarray[int]
    classes = list(le.classes_)        # 与 0..C-1 的对应关系

    # 3) 转成 torch.long，并返回一个（索引→标签）的对齐方案
    # y = torch.tensor(y, dtype=torch.long)

    return y, classes, index_keep


def gmm_cluster(X, k_range=range(2, 31), covariance_type='full',
                reg_covar=1e-6, random_state=0):
    Xs = StandardScaler().fit_transform(X)
    best_bic, best_gmm = np.inf, None
    for k in k_range:
        gmm = GaussianMixture(n_components=k, covariance_type=covariance_type,
                              reg_covar=reg_covar, random_state=random_state)
        gmm.fit(Xs)
        bic = gmm.bic(Xs)
        if bic < best_bic:
            best_bic, best_gmm = bic, gmm
    labels = best_gmm.predict(Xs)              # 硬标签
    probs  = best_gmm.predict_proba(Xs)        # 软标签（可用于权重）
    return labels, probs, best_gmm.n_components


def gmm_cluster_fixed_k(X, k, covariance_type='full',
                        reg_covar=1e-6, random_state=0):
    """
    使用指定的聚类簇数量 k 对数据 X 进行 GMM 聚类。

    参数:
    X (array-like): 待聚类的数据。
    k (int):         要创建的聚类簇的数量。
    covariance_type (str): 协方差类型，可选 'full', 'tied', 'diag', 'spherical'。
    reg_covar (float):     添加到协方差对角线以保证其正定性的非负正则化参数。
    random_state (int):    用于随机数生成的种子，确保结果可复现。

    返回:
    labels (array):    每个样本的硬聚类标签。
    probs (array):     每个样本属于各个聚类的概率（软标签）。
    gmm (object):      训练好的 GaussianMixture 模型实例。
    """
    # 1. 数据标准化
    Xs = StandardScaler().fit_transform(X)

    # 2. 初始化并训练GMM模型（直接使用指定的k）
    gmm = GaussianMixture(n_components=k, covariance_type=covariance_type,
                          reg_covar=reg_covar, random_state=random_state)
    gmm.fit(Xs)

    # 3. 预测结果
    labels = gmm.predict(Xs)  # 硬标签
    probs = gmm.predict_proba(Xs)  # 软标签（可用于权重）

    # 4. 返回标签、概率和训练好的模型
    return labels, probs, gmm

def set_seed():
    # seed
    seed = 41
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    dgl.random.seed(seed)


def cal_spatial_exp(
        adata: AnnData,
        layer_key: Optional[str] = None,
        is_pca: bool = False,
        n_comps: int = 50,
        mode: str = 'KNN',
        rad_cutoff: Optional[float] = 20,
        k_cutoff: Optional[float] = 20,
        verbose: bool = True):

    assert (mode.lower() in ['radius', 'knn']), 'mode must be `radius` or `knn`!'
    # adata.layers['data'] = adata.X.copy()
    if verbose:
        print("-------Calculating Neighboring expression...")

    coord = pd.DataFrame({'x': adata.obsm['spatial'][:, 0], 'y': adata.obsm['spatial'][:, 1]})

    if mode.lower() == 'radius':
        nbr = NearestNeighbors(radius=rad_cutoff).fit(coord)
        _, indices = nbr.radius_neighbors(coord)
    elif mode.lower() == 'knn':
        nbr = NearestNeighbors(n_neighbors=k_cutoff + 1).fit(coord)
        _, indices = nbr.kneighbors(coord)
        indices = np.delete(indices, 0, axis=1)

    # cell * gene
    if layer_key is not None:
        data_raw = adata.obsm[layer_key].copy()
    else:
        if issparse(adata.X):
            data_raw = adata.X.toarray().copy()
        else:
            data_raw = adata.X.copy()
    data_nbr = []
    for i in range(indices.shape[0]):
        data_nbr_tmp = data_raw[indices[i]].mean(axis=0)
        data_nbr.append(data_nbr_tmp)
    data_nbr = np.array(data_nbr)

    if is_pca:
        data_raw = PCA(n_components=n_comps).fit_transform(data_raw)
        data_nbr = PCA(n_components=n_comps).fit_transform(data_nbr)

    adata.obsm['X_data'] = data_raw
    adata.obsm['X_data_nbr'] = data_nbr

    if verbose:
        print("Calculating done.")

    return adata


def construct_graph(
        data: np.ndarray,
        knn: int = 20,
        mik: int = 5):

    # knn
    train_neighbors = NearestNeighbors(n_neighbors=knn + 1, metric='euclidean').fit(data)
    _, idx = train_neighbors.kneighbors(data)

    # adj
    adj = train_neighbors.kneighbors_graph(data)
    adj = adj + adj.T.multiply(adj.T > adj) - adj.multiply(adj.T > adj)

    g = dgl.from_scipy(adj)
    g.ndata['feat'] = torch.FloatTensor(data).to(torch.float32)
    g.ndata['adj'] = convert_adj(adj)

    return g


def convert_adj(sparse_mat):
    """
    Convert `scipy.sparse.matrix` to `torch.sparse.tensor`
    """
    sparse_mat = sparse_mat.tocoo().astype(np.float32)
    indices = torch.from_numpy(np.vstack((sparse_mat.row, sparse_mat.col)).astype(np.int64))
    values = torch.from_numpy(sparse_mat.data)
    shape = torch.Size(sparse_mat.shape)
    return torch.sparse.FloatTensor(indices, values, shape)


def shuffling(x, latent, device):
    idx = torch.arange(0, x.shape[0]).to(device)
    idx2 = torch.randperm(idx.size(0)).to(device)
    idx_shuffling = idx[idx2].unsqueeze(1)
    idx_shuffling = idx_shuffling.repeat(1, latent)
    return torch.gather(x, 0, idx_shuffling)


# left_cell_num < batch_size
def random_split(n, m):
    nums = list(range(n))
    random.shuffle(nums)
    return [nums[i:i + m] for i in range(0, n, m)]


# left_cell_num > batch_size
def random_split2(n, batch_num):
    nums = list(range(n))
    random.shuffle(nums)

    batch_size = n // (batch_num + 1)
    result = [nums[i * batch_size: (i + 1) * batch_size] for i in range(batch_num)]
    result.append(nums[batch_num * batch_size:])

    return result


class myDataset(Dataset):
    def __init__(self, g_list):
        self.g_list = g_list

    def __getitem__(self, idx):

        return tuple(g[idx] for g in self.g_list)

    def __len__(self):
        return len(self.g_list[0])
    
from dotenv import load_dotenv
load_dotenv("../.env")
# --- OSS 配置 (从环境变量读取，更安全) ---
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT") # 例如 'oss-cn-hangzhou.aliyuncs.com'
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")

# 初始化 OSS Auth 和 Bucket
auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

def upload_data_to_oss(data: bytes, object_name: str) -> str:
    """ Generic helper to upload bytes data to OSS. """
    bucket.put_object(object_name, data)
    return f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{object_name}"

def upload_plot_to_oss(fig, object_name: str) -> str:
    """
    将 matplotlib figure 对象上传到 OSS 并返回公开 URL
    :param fig: matplotlib 的 Figure 对象
    :param object_name: 在 OSS 中保存的文件路径，例如 'results/task123.png'
    :return: 公开可访问的 URL
    """
    # 1. 将图像保存到内存中的 BytesIO 对象
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight') # bbox_inches='tight' 裁剪掉多余白边
    buffer.seek(0) # 重置指针到开头

    # 2. 上传到 OSS
    bucket.put_object(object_name, buffer)
    plt.close(fig) # 关闭 figure 释放内存

    # 3. 构建并返回公开 URL
    # 格式: https://<BucketName>.<Endpoint>/<ObjectName>
    public_url = f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{object_name}"
    return public_url
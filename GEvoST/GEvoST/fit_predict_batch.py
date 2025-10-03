import numpy as np
import torch
# from numpy.distutils.system_info import gdk_pixbuf_xlib_2_info
from torch.utils.data import Dataset, DataLoader, TensorDataset
from typing import Tuple
from scipy.spatial.distance import pdist
import phenograph
import scanpy as sc
from sklearn.decomposition import PCA
import dgl
from preprocess import prepare_data
from triplet_loss_torch import soft_triplet_batch_all_sampled
from utils import cal_spatial_exp, gmm_cluster, labels_from_obs
from model_architecture_torch import Model


def _move_graph_to_device(g, device):
    """根据你的图对象类型自行调整。若 g 是 PyG/Data 或稀疏张量，需要对应 to(device)。"""
    try:
        return g.to(device)
    except AttributeError:
        # 如果是普通张量/稀疏张量
        return g.to(device) if hasattr(g, 'to') else g

@torch.no_grad()
def _infer_all(
    model,
    n_hidden,
    latent_dim,
    data_x: np.ndarray,
    data_y: np.ndarray,
    batch_idx_list,
    dataloader,
    device: str,
):
    """
    遍历所有 batch，收集 (z, xh, yh, hx, hy) 到全局数组（与原顺序对齐）。
    要求：dataloader 的迭代顺序与 batch_idx_list 对齐；dataloader 每次产出 [g_x_b, g_y_b]。
    """
    model.eval()
    N = data_x.shape[0]
    # 先占位
    z_all   = np.zeros((N, latent_dim), dtype=np.float32)
    hx_all  = np.zeros((N, n_hidden), dtype=np.float32)   # 假设 Model 中 h 维度为 n_hidden
    hy_all  = np.zeros((N, n_hidden), dtype=np.float32)
    xh_all  = np.zeros_like(data_x, dtype=np.float32)
    yh_all  = np.zeros_like(data_y, dtype=np.float32)

    bx_iter = iter(batch_idx_list)

    for batch_graphs in dataloader:
        idx = next(bx_iter)                         # 全局索引
        xb_np = data_x[idx]
        yb_np = data_y[idx]
        xb = torch.from_numpy(xb_np).float().to(device)
        yb = torch.from_numpy(yb_np).float().to(device)

        # 取图（这里假设 batch_graphs 是 list/tuple: [g_x_b, g_y_b]）
        if isinstance(batch_graphs, (list, tuple)):
            g_x_b, g_y_b = batch_graphs[0], batch_graphs[1]
        elif isinstance(batch_graphs, dict):
            g_x_b, g_y_b = batch_graphs['g_list'][0], batch_graphs['g_list'][1]
        else:
            raise TypeError("Unsupported batch_graphs type; please adapt _infer_all unpacking.")
        g_x_b = _move_graph_to_device(g_x_b, device)
        g_y_b = _move_graph_to_device(g_y_b, device)

        z, xh, yh, hx, hy, _ = model(xb, yb, g_x=g_x_b, g_y=g_y_b)

        z_all[idx]  = z.detach().cpu().numpy()
        xh_all[idx] = xh.detach().cpu().numpy()
        yh_all[idx] = yh.detach().cpu().numpy()
        hx_all[idx] = hx.detach().cpu().numpy()
        hy_all[idx] = hy.detach().cpu().numpy()

    return z_all, xh_all, yh_all, hx_all, hy_all

def _estimate_margin_sampled(z: np.ndarray, top_frac: float = 0.2, max_pairs: int = 200000, rng: int = 123) -> float:
    """
    采样估计 margin，避免 O(N^2) OOM。
    在全局 z 上随机采样若干对，取上分位与下分位差。
    """
    N = z.shape[0]
    rs = np.random.RandomState(rng)
    # 采样对数（含自适应上限）
    P = min(max_pairs, N * (N - 1) // 2)
    # 用随机索引采样一组 (i,j)
    idx_i = rs.randint(0, N, size=P)
    idx_j = rs.randint(0, N, size=P)
    mask = idx_i != idx_j
    idx_i, idx_j = idx_i[mask], idx_j[mask]

    # 计算欧式距离（也可先把 z L2 normalize 后用余弦距离）
    diffs = z[idx_i] - z[idx_j]
    d = np.sqrt((diffs * diffs).sum(axis=1))

    d_sort = np.sort(d)
    k = max(1, int(len(d_sort) * top_frac))
    m = float(np.median(d_sort[-k:]) - np.median(d_sort[:k]))
    return max(m, 1e-6)  # 防止异常为负/过小

def model_fit_predict_batch(adata,
                      cluster_key_ct=None,
                      cluster_key_dom=None,
                      GT=True,
                      pca_dim=20,

                      ## model paras
                      n_hidden=128,
                      latent_dim: int = 100,
                      learn_rate=1e-4,
                      n_epochs_init=200,
                      n_epochs_refine=200,  # 新增：专门给参考标签 refine 的轮数
                      n_epochs_soft=500,

                      ## balanced paras
                      lambda_regul: float = 1.0,
                      lambda_super: float = 1.0,
                      dgi_lambda: float = 1.0,

                      ## GMM 相关
                      soft_label=True,
                      k_range_x=range(5, 15),  # 你给的 A 视图 K 搜索范围
                      k_range_y=range(2, 5),  # 你给的 B 视图 K 搜索范围
                      gmm_covariance_type: str = 'full',
                      gmm_reg_covar: float = 1e-5,
                      gmm_update_every: int = 200,  # 软阶段每多少 epoch 刷新一次 GMM
                      verbose: bool = True,
                      device='cuda') -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns:
        latent, reconstruct_x, reconstruct_y, latent_x, latent_y (as numpy arrays)
        x: for gene expression
        y: for spatial
    """

    # ====== 1) 取数据/批信息 ======
    assert 'batch_idx' in adata.uns and 'dataloader' in adata.uns, \
        "请先调用 prepare_data_batch(...) 在 adata.uns 中构建 batch_idx 和 dataloader"

    batch_idx_list = adata.uns['batch_idx']  # List[List[int]]
    dataloader = adata.uns['dataloader']  # GraphDataLoader, len == batch_num
    batch_num = len(batch_idx_list)

    data_x = adata.obsm['X_data']
    data_y = adata.obsm['X_data_nbr']

    # ====== 2) 用 PCA 仅用于初始化标签 ======
    view_x_feature = PCA(n_components=pca_dim).fit_transform(data_x)
    view_y_feature = PCA(n_components=pca_dim).fit_transform(data_y)

    if GT:
        # ## GT
        view_x_label, cls_x, idx_keep_x = labels_from_obs(adata, cluster_key_ct, drop_na=True)
        view_y_label, cls_y, idx_keep_y = labels_from_obs(adata, cluster_key_dom, drop_na=True)
    else:
        # ## phenograph
        # view_a_label, _, _ = phenograph.cluster(view_a_feature)
        # view_b_label, _, _ = phenograph.cluster(view_b_feature)

        # ## GMM
        view_x_label, prob_x, kx = gmm_cluster(view_x_feature, k_range=k_range_x)  # cell type
        view_y_label, prob_y, ky = gmm_cluster(view_y_feature, k_range=k_range_y)  # spatial domain

    # ## Combined analysis using model
    label_x_full = torch.from_numpy(view_x_label).long().to(device)
    label_y_full = torch.from_numpy(view_y_label).long().to(device)

    # === Hyper-params  ===
    feature_dim_x = data_x.shape[1]
    feature_dim_y = data_y.shape[1]

    # 2) 初始化模型时指定 encoder_type='dgi'
    model = Model(feature_dim_x, feature_dim_y, n_hidden, latent_dim,
                  encoder_type='dgi', gnn_layers=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learn_rate)

    # -------- Phase 1：仅重构（+DGI+F范数），无 triplet（按 batch 训练） --------
    print('======== (mini-batch): Phase 1: initialization (reconstruction only) ========')
    model.train()
    for epoch in range(n_epochs_init):
        # 遍历所有 batch
        bx_iter = iter(batch_idx_list)
        for batch_graphs in dataloader:
            idx = next(bx_iter)
            xb = torch.from_numpy(data_x[idx]).float().to(device)
            yb = torch.from_numpy(data_y[idx]).float().to(device)

            if isinstance(batch_graphs, (list, tuple)):
                g_x_b, g_y_b = batch_graphs[0], batch_graphs[1]
            elif isinstance(batch_graphs, dict):
                g_x_b, g_y_b = batch_graphs['g_list'][0], batch_graphs['g_list'][1]
            else:
                raise TypeError("Unsupported batch_graphs type; please adapt unpacking.")

            g_x_b = _move_graph_to_device(g_x_b, device)
            g_y_b = _move_graph_to_device(g_y_b, device)

            loss, rec, sp, _, _, dgi = model.compute_losses(
                xb, yb,
                label_x=torch.zeros(xb.shape[0], dtype=torch.long, device=device),
                label_y=torch.zeros(yb.shape[0], dtype=torch.long, device=device),
                triplet_margin=0.0,
                weight_penalty=lambda_regul,
                triplet_lambda=0.0,
                dgi_lambda=dgi_lambda,
                g_x=g_x_b,
                g_y=g_y_b
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if epoch % 50 == 0:
                print(
                    f'[init] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} sp={sp.item():.5f} dgi={dgi.item():.5f}')

    # ======== 估计 margin（基于当前 z） ========
    print('======== Estimate the margin for the triplet loss ======== ')
    z_all, _, _, _, _ = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)
    margin_estimate = _estimate_margin_sampled(z_all, top_frac=0.2, max_pairs=200000, rng=123)

    # latent_pd = pdist(latent_np, metric='euclidean')
    # latent_pd_sort = np.sort(latent_pd)
    # select_top_n = int(latent_pd_sort.size * 0.2)
    # if select_top_n < 1:
    #     select_top_n = max(1, latent_pd_sort.size // 5)
    # margin_estimate = np.median(latent_pd_sort[-select_top_n:]) - np.median(latent_pd_sort[:select_top_n])
    # margin_estimate = float(margin_estimate)
    print(f'Estimated margin = {margin_estimate:.4f}')

    # -------- Phase 2：参考硬标签 refine（按 batch）--------
    print('======== (mini-batch): Phase 2: refinement with provided hard labels ========')
    for epoch in range(n_epochs_refine):
        model.train()
        bx_iter = iter(batch_idx_list)
        for batch_graphs in dataloader:
            idx = next(bx_iter)
            xb = torch.from_numpy(data_x[idx]).float().to(device)
            yb = torch.from_numpy(data_y[idx]).float().to(device)

            # 从全局标签切片
            lbx = label_x_full[idx]
            lby = label_y_full[idx]

            if isinstance(batch_graphs, (list, tuple)):
                g_x_b, g_y_b = batch_graphs[0], batch_graphs[1]
            elif isinstance(batch_graphs, dict):
                g_x_b, g_y_b = batch_graphs['g_list'][0], batch_graphs['g_list'][1]
            else:
                raise TypeError("Unsupported batch_graphs type; please adapt unpacking.")
            g_x_b = _move_graph_to_device(g_x_b, device)
            g_y_b = _move_graph_to_device(g_y_b, device)

            loss, rec, sp, tx, ty, dgi = model.compute_losses(
                xb, yb, lbx, lby,
                triplet_margin=margin_estimate,
                weight_penalty=lambda_regul,
                triplet_lambda=lambda_super,
                dgi_lambda=dgi_lambda,
                g_x=g_x_b,
                g_y=g_y_b
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if epoch % 50 == 0:
            print(f'[refine] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} sp={sp.item():.5f} '
                  f'tx={tx.item():.5f} ty={ty.item():.5f} dgi={dgi.item():.5f}')


    # -------- Phase 3：GMM 软标签 + 软三元组（周期性刷新 GMM）--------
    tag = 'soft-label' if soft_label else 'hard-label'
    print(f'======== Phase 3 (mini-batch): {tag} training with GMM ========')
    # 先做一次全局前向，基于 h_x/h_y 初始化 GMM
    _, _, _, hx_all, hy_all = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)
    if soft_label:
        ## soft label
        _, prob_x_np, kx = gmm_cluster(hx_all, k_range=k_range_x,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        _, prob_y_np, ky = gmm_cluster(hy_all, k_range=k_range_y,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        prob_x_full = torch.from_numpy(prob_x_np).to(device)
        prob_y_full = torch.from_numpy(prob_y_np).to(device)
        print(f'[GMM init] Kx={kx} Ky={ky}')

        for epoch in range(1, n_epochs_soft + 1):
            model.train()
            bx_iter = iter(batch_idx_list)
            for batch_graphs in dataloader:
                idx = next(bx_iter)
                xb = torch.from_numpy(data_x[idx]).float().to(device)
                yb = torch.from_numpy(data_y[idx]).float().to(device)
                px = prob_x_full[idx]
                py = prob_y_full[idx]

                if isinstance(batch_graphs, (list, tuple)):
                    g_x_b, g_y_b = batch_graphs[0], batch_graphs[1]
                elif isinstance(batch_graphs, dict):
                    g_x_b, g_y_b = batch_graphs['g_list'][0], batch_graphs['g_list'][1]
                else:
                    raise TypeError("Unsupported batch_graphs type; please adapt unpacking.")
                g_x_b = _move_graph_to_device(g_x_b, device)
                g_y_b = _move_graph_to_device(g_y_b, device)

                z, xh, yh, hx, hy, dgi = model(xb, yb, g_x=g_x_b, g_y=g_y_b)
                # 重构
                xmask = (xb != 0).float()
                denom = torch.clamp(xmask.sum(), min=1.0)
                rec_x = torch.norm(xmask * (xh - xb)) / denom
                rec_y = torch.norm(yh - yb)
                rec = rec_x + rec_y
                # F 范数
                sp = torch.norm(model.w_selection_x, p='fro') + torch.norm(model.w_selection_y, p='fro')
                # 软 triplet（用概率）
                # trip = soft_triplet_batch_all(z, prob_x, prob_y, margin_estimate)
                trip = soft_triplet_batch_all_sampled(z, px, py, margin_estimate, top_pos=500, top_neg=500)
                loss = rec + lambda_regul * sp + lambda_super * trip + dgi_lambda * dgi

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            # 周期性刷新 GMM（在最新 h_x/h_y 上）
            if (epoch % gmm_update_every) == 0:
                _, _, _, hx_all, hy_all = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)

                _, prob_x_np, kx = gmm_cluster(hx_all, k_range=k_range_x, covariance_type=gmm_covariance_type,
                                               reg_covar=gmm_reg_covar)
                _, prob_y_np, ky = gmm_cluster(hy_all, k_range=k_range_y, covariance_type=gmm_covariance_type,
                                               reg_covar=gmm_reg_covar)
                prob_x_full = torch.from_numpy(prob_x_np).to(device)
                prob_y_full = torch.from_numpy(prob_y_np).to(device)
                if verbose:
                    print(f'  [GMM refresh] ep={epoch} Kx={kx} Ky={ky}')

                # # 可选：动态重估 margin（若不想变动训练稳定性，可以跳过）
                # margin_estimate = _estimate_margin_sampled(
                #     _infer_all(model, data_x, data_y, batch_idx_list, dataloader, device)[0],
                #     top_frac=0.2, max_pairs=200000, rng=123
                # )

            if verbose and (epoch % 50 == 0):
                print(f'[soft] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} '
                      f'sp={sp.item():.5f} tri={trip.item():.5f} dgi={dgi.item():.5f}')
    else:
        # ## hard label
        # 初始软标签（基于最新的 h_x/h_y）
        _, _, _, hx_all, hy_all = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)

        label_x_np, prob_x_np, kx = gmm_cluster(hx_all, k_range=k_range_x, covariance_type=gmm_covariance_type,
                                             reg_covar=gmm_reg_covar)
        label_y_np, prob_y_np, ky = gmm_cluster(hy_all, k_range=k_range_y, covariance_type=gmm_covariance_type,
                                             reg_covar=gmm_reg_covar)
        label_x_full = torch.from_numpy(label_x_np).long().to(device)
        label_y_full = torch.from_numpy(label_y_np).long().to(device)
        print(f'[GMM init] Kx={kx} Ky={ky}')

        for epoch in range(1, n_epochs_soft + 1):
            model.train()
            bx_iter = iter(batch_idx_list)
            for batch_graphs in dataloader:
                idx = next(bx_iter)
                xb = torch.from_numpy(data_x[idx]).float().to(device)
                yb = torch.from_numpy(data_y[idx]).float().to(device)
                lbx = label_x_full[idx]
                lby = label_y_full[idx]

                if isinstance(batch_graphs, (list, tuple)):
                    g_x_b, g_y_b = batch_graphs[0], batch_graphs[1]
                elif isinstance(batch_graphs, dict):
                    g_x_b, g_y_b = batch_graphs['g_list'][0], batch_graphs['g_list'][1]
                else:
                    raise TypeError("Unsupported batch_graphs type; please adapt unpacking.")
                g_x_b = _move_graph_to_device(g_x_b, device)
                g_y_b = _move_graph_to_device(g_y_b, device)


                loss, rec, sp, tx, ty, dgi = model.compute_losses(
                    xb, yb, lbx, lby,
                    triplet_margin=margin_estimate,
                    weight_penalty=lambda_regul,
                    triplet_lambda=lambda_super,
                    dgi_lambda=dgi_lambda,
                    g_x=g_x_b,
                    g_y=g_y_b
                )

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            # 周期性刷新 GMM（在最新 h_x/h_y 上）
            if (epoch % gmm_update_every) == 0:
                _, _, _, hx_all, hy_all = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)

                label_x_np, prob_x_np, kx = gmm_cluster(hx_all, k_range=k_range_x,
                                                     covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                label_x_np, prob_y_np, ky = gmm_cluster(hy_all, k_range=k_range_y,
                                                     covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                label_x_full = torch.from_numpy(label_x_np).long().to(device)
                label_y_full = torch.from_numpy(label_y_np).long().to(device)
                if verbose:
                    print(f'  [GMM refresh] ep={epoch} Kx={kx} Ky={ky}')

            if verbose and (epoch % 50 == 0):
                print(f'[hard] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} '
                      f'sp={sp.item():.5f} tri_x={tx.item():.5f} tri_y={ty.item():.5f} dgi={dgi.item():.5f}')

    # ======== 推理输出：建议全图一次前向拿到完整嵌入与重构 ========
    print('======== Inference (global over batches) ========')
    model.eval()
    z_all, xh_all, yh_all, hx_all, hy_all = _infer_all(model, n_hidden, latent_dim, data_x, data_y, batch_idx_list, dataloader, device)
    print('++++++++++ Model (PyTorch, full/subgraph) completed ++++++++++')
    return  z_all, xh_all, yh_all, hx_all, hy_all


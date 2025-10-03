import torch
import os
from res_clustering_visualization import clustering_visualization
from fit_predict_batch import model_fit_predict_batch
import scanpy as sc
from sklearn.decomposition import PCA
from utils import gmm_cluster_fixed_k, set_seed
from preprocess import prepare_data, prepare_data_batch
from utils import cal_spatial_exp, gmm_cluster, labels_from_obs


if __name__ == '__main__':
    set_seed()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    k_nbrs = 15
    batch_num = 30
    GT = True

    # ## load data
    adata = sc.read('/data/chenjm/home/e1518797/codes/SPaCENET/data/scNiche_data/BALBc-1.h5ad')
    sc.pp.scale(adata)
    print(adata)

    # ## preprocess
    adata = cal_spatial_exp(adata=adata, mode='KNN', k_cutoff=k_nbrs, is_pca=False, verbose=False)
    adata = prepare_data_batch(adata=adata, verbose=False, batch_num=batch_num)

    # ## prepare original clustering labels
    n_cell_type = len(set(adata.obs['CellType']))  # 27 cell types
    n_domains = len(set(adata.obs['Compartment']))  # 4 domains

    z, rec_x, rec_y, \
        z_x, z_y = model_fit_predict_batch(
                                adata,
                                cluster_key_ct='CellType',
                                cluster_key_dom='Compartment',
                                GT=GT,
                                pca_dim=20,

                                ## model paras
                                n_hidden=64,
                                latent_dim=16,
                                learn_rate = 1e-4,
                                n_epochs_init = 400,
                                n_epochs_refine = 400,  # 新增：专门给参考标签 refine 的轮数
                                n_epochs_soft = 900,

                                ## balanced paras
                                lambda_regul=1.0,
                                lambda_super=1.0,
                                dgi_lambda=1.0,

                                ## GMM 相关
                                soft_label=False,
                                k_range_x = range(2, 30),  # 你给的 A 视图 K 搜索范围
                                k_range_y = range(2, 5),  # 你给的 B 视图 K 搜索范围
                                gmm_covariance_type='full',
                                gmm_reg_covar=1e-6,
                                gmm_update_every=500,  # 软阶段每多少 epoch 刷新一次 GMM
                                verbose=True,
                                device='cuda'
                                )

    if GT:
        # GT 为 True 时执行这里的代码
        save_root = 'results/CODEX_Mouse_slpeen/with_label/'
    else:
        # GT 为 False 时执行这里的代码
        save_root = 'results/CODEX_Mouse_slpeen/without_label/'
    print(f"结果将保存在: {save_root}")

    # 检查并创建目录
    if not os.path.exists(save_root):
        os.makedirs(save_root)  # 推荐使用 os.makedirs，可以递归创建多层不存在的目录
        print(f"目录已创建: {save_root}")
    else:
        print(f"目录已存在: {save_root}")

    (adata,
     ari_x_vs_ct, ari_y_vs_dom, ari_z_vs_ct, ari_z_vs_dom,
     nmi_x_vs_ct, nmi_y_vs_dom, nmi_z_vs_ct, nmi_z_vs_dom) = clustering_visualization(adata,
                                                                                      cluster_key_ct='CellType',
                                                                                      cluster_key_dom='Compartment',
                                                                                      n_cell_type=n_cell_type,
                                                                                      n_domains=n_domains,
                                                                                      z=z,
                                                                                      z_x=z_x,
                                                                                      z_y=z_y,
                                                                                      k=10,
                                                                                      save_path=save_root
                                                                                      )
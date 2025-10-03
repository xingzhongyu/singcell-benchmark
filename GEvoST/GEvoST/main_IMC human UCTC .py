import pathlib
import torch
from fit_predict import model_fit_predict
import scanpy as sc
from utils import set_seed, cal_spatial_exp, upload_data_to_oss
from preprocess import prepare_data
# from res_clustering_visualization import clustering_visualization
from res_clustering_visualization_scanpy_color import clustering_visualization
import os

if __name__ == '__main__':
    set_seed()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    k_nbrs = 30
    GT=True

    # ## load data
    adata = sc.read('../data/UTUC.h5ad')
    roi_name = '20200923_PM784_A5-02'
    print(f"\n=== Processing ROI: {roi_name} ===")
    safe_roi_name = roi_name.replace("/", "_").replace("\\", "_")

    adata = adata[adata.obs['roi'] == roi_name]
    print(adata)

    # ## preprocess
    adata = cal_spatial_exp(adata=adata, mode='KNN', k_cutoff=k_nbrs, is_pca=False, verbose=False)
    adata = prepare_data(adata=adata, verbose=False)

    # ## prepare original clustering labels
    n_cell_type = len(set(adata.obs['cell_type_broad']))  # 10 cell types
    n_domains = len(set(adata.obs['topological_domain']))  # 2 domains

    z, rec_x, rec_y, \
        z_x, z_y = model_fit_predict(
                                adata,
                                cluster_key_ct='cell_type_broad',
                                cluster_key_dom='topological_domain',
                                GT=GT,
                                pca_dim=20,

                                ## model paras
                                n_hidden=64,
                                latent_dim=16,
                                learn_rate = 1e-4,
                                n_epochs_init = 200,
                                n_epochs_refine = 200,  # 新增：专门给参考标签 refine 的轮数
                                n_epochs_soft = 900,

                                ## balanced paras
                                lambda_regul=1.0,
                                lambda_super=1.0,
                                dgi_lambda=1.0,

                                ## GMM 相关
                                soft_label=False,
                                k_range_x = range(2, 30),  # 你给的 A 视图 K 搜索范围
                                k_range_y = range(2, 10),  # 你给的 B 视图 K 搜索范围
                                gmm_covariance_type='full',
                                gmm_reg_covar=1e-6,
                                gmm_update_every=500,  # 软阶段每多少 epoch 刷新一次 GMM
                                verbose=True,
                                device=device
                                )

    if GT:
        # GT 为 True 时执行这里的代码
        save_root = 'results/IMC_Human_UCTC/with_label/'
    else:
        # GT 为 False 时执行这里的代码
        save_root = 'results/IMC_Human_UCTC/without_label/'
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
                                                                                      cluster_key_ct='cell_type_broad',
                                                                                      cluster_key_dom='topological_domain',
                                                                                      n_cell_type=n_cell_type,
                                                                                      n_domains=n_domains,
                                                                                      z=z,
                                                                                      z_x=z_x,
                                                                                      z_y=z_y,
                                                                                      k_pg=50,
                                                                                      s_scatter=6,
                                                                                      s_spatial=20,
                                                                                      refinement=False,
                                                                                      save_path=save_root
                                                                                      )
    p=pathlib.Path(save_root)
    for png_file in p.rglob('*.png'):
        key=png_file.name
        value=png_file.read_bytes()
        url=upload_data_to_oss(value,key)
        print(f"Uploaded {key} to {url}")




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


def model_fit_predict(adata,
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
                      gmm_reg_covar: float = 1e-6,
                      gmm_update_every: int = 200,  # 软阶段每多少 epoch 刷新一次 GMM
                      verbose: bool = True,
                      device='cuda') -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns:
        latent, reconstruct_x, reconstruct_y, latent_x, latent_y (as numpy arrays)
        x: for gene expression
        y: for spatial
    """
    # ## Preprocess data
    g_x = adata.uns['g_X_data']  # expression graph
    g_y = adata.uns['g_X_data_nbr']  # spatial nbr expression graph

    data_x = adata.obsm['X_data']
    data_y = adata.obsm['X_data_nbr']

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
    data_x = torch.from_numpy(data_x).float()
    data_y = torch.from_numpy(data_y).float()
    label_x = torch.from_numpy(view_x_label).long()
    label_y = torch.from_numpy(view_y_label).long()

    # === Hyper-params (kept the same values as TF implementation) ===
    N = data_x.shape[0]
    feature_dim_x = data_x.shape[1]
    feature_dim_y = data_y.shape[1]

    xb = data_x.to(device)
    yb = data_y.to(device)
    label_x = label_x.to(device)
    label_y = label_y.to(device)
    g_x = g_x.to(device)
    g_y = g_y.to(device)

    # 2) 初始化模型时指定 encoder_type='dgi'
    model = Model(feature_dim_x, feature_dim_y, n_hidden, latent_dim,
                 encoder_type='dgi', gnn_layers=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learn_rate)

    # -------- Phase 1：仅重构（+DGI+F范数），无 triplet --------
    print('======== Phase 1: initialization (reconstruction only) ========')
    model.train()
    for epoch in range(n_epochs_init):
        loss, rec, sp, _, _, dgi = model.compute_losses(
            xb, yb,
            label_x=torch.zeros(N, dtype=torch.long, device=device),
            label_y=torch.zeros(N, dtype=torch.long, device=device),
            triplet_margin=0.0,
            weight_penalty=lambda_regul,
            triplet_lambda=0.0,
            dgi_lambda=dgi_lambda,
            g_x=g_x,
            g_y=g_y
        )
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if epoch % 50 == 0:
            print(f'[init] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} sp={sp.item():.5f} dgi={dgi.item():.5f}')

    # ======== 估计 margin（基于当前 z） ========
    print('======== Estimate the margin for the triplet loss ======== ')
    model.eval()
    with torch.no_grad():
        z, _, _, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
        latent_np = z.detach().cpu().numpy()
        # margin_estimate = _estimate_margin_z(z.detach().cpu().numpy())
        latent_pd = pdist(latent_np, metric='euclidean')
        latent_pd_sort = np.sort(latent_pd)
        select_top_n = int(latent_pd_sort.size * 0.2)
        if select_top_n < 1:
            select_top_n = max(1, latent_pd_sort.size // 5)
        margin_estimate = np.median(latent_pd_sort[-select_top_n:]) - np.median(latent_pd_sort[:select_top_n])
        margin_estimate = float(margin_estimate)
        print(f'Estimated margin = {margin_estimate:.4f}')

    # -------- Phase 2：参考硬标签 refine（只在这一步用 label_x/label_y）--------
    print('======== Phase 2: refinement with provided hard labels ========')
    model.train()
    for epoch in range(n_epochs_refine):
        loss, rec, sp, tx, ty, dgi = model.compute_losses(
            xb, yb, label_x, label_y,
            triplet_margin=margin_estimate,
            weight_penalty=lambda_regul,
            triplet_lambda=lambda_super,
            dgi_lambda=dgi_lambda,
            g_x=g_x,
            g_y=g_y
        )
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if epoch % 50 == 0:
            print(f'[refine] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} sp={sp.item():.5f} '
                  f'tx={tx.item():.5f} ty={ty.item():.5f} dgi={dgi.item():.5f}')

    if soft_label:
        ## soft label
        # -------- Phase 3：GMM 软标签 + 软三元组（周期性刷新 GMM）--------
        print('======== Phase 3: soft-label training with GMM (periodic refresh) ========')
        # 初始软标签（基于最新的 h_x/h_y）
        model.eval()
        with torch.no_grad():
            _, _, _, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
        _, prob_x_np, kx = gmm_cluster(hx.detach().cpu().numpy(), k_range=k_range_x,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        _, prob_y_np, ky = gmm_cluster(hy.detach().cpu().numpy(), k_range=k_range_y,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        prob_x = torch.from_numpy(prob_x_np).to(device)
        prob_y = torch.from_numpy(prob_y_np).to(device)
        print(f'[GMM init] Kx={kx} Ky={ky}')

        model.train()
        for epoch in range(1, n_epochs_soft+1):
            z, xh, yh, hx, hy, dgi = model(xb, yb, g_x=g_x, g_y=g_y)
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
            trip = soft_triplet_batch_all_sampled(z, prob_x, prob_y, margin_estimate, top_pos=500, top_neg=500)
            loss = rec + lambda_regul * sp + lambda_super * trip + dgi_lambda * dgi

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # 周期性刷新 GMM（在最新 h_x/h_y 上）
            if (epoch % gmm_update_every) == 0:
                model.eval()
                with torch.no_grad():
                    z, _, _, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
                _, prob_x_np, kx = gmm_cluster(hx.detach().cpu().numpy(), k_range=k_range_x,
                                               covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                _, prob_y_np, ky = gmm_cluster(hy.detach().cpu().numpy(), k_range=k_range_y,
                                               covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                prob_x = torch.from_numpy(prob_x_np).to(device)
                prob_y = torch.from_numpy(prob_y_np).to(device)
                if verbose:
                    print(f'  [GMM refresh] ep={epoch} Kx={kx} Ky={ky}')

                # # ******************************************************************************************************
                # latent_np = z.detach().cpu().numpy()
                # # margin_estimate = _estimate_margin_z(z.detach().cpu().numpy())
                # latent_pd = pdist(latent_np, metric='euclidean')
                # latent_pd_sort = np.sort(latent_pd)
                # select_top_n = int(latent_pd_sort.size * 0.2)
                # if select_top_n < 1:
                #     select_top_n = max(1, latent_pd_sort.size // 5)
                # margin_estimate = np.median(latent_pd_sort[-select_top_n:]) - np.median(latent_pd_sort[:select_top_n])
                # margin_estimate = float(margin_estimate)
                # print(f'Estimated margin = {margin_estimate:.4f}')

            if verbose and (epoch % 50 == 0):
                print(f'[soft] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} '
                      f'sp={sp.item():.5f} tri={trip.item():.5f} dgi={dgi.item():.5f}')
    else:
        # ## hard label
        # -------- Phase 3：GMM 软标签 + 软三元组（周期性刷新 GMM）--------
        print('======== Phase 3: soft-label training with GMM (periodic refresh) ========')
        # 初始软标签（基于最新的 h_x/h_y）
        with torch.no_grad():
            _, _, _, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
        label_x, prob_x_np, kx = gmm_cluster(hx.detach().cpu().numpy(), k_range=k_range_x,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        label_y, prob_y_np, ky = gmm_cluster(hy.detach().cpu().numpy(), k_range=k_range_y,
                                       covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
        label_x = torch.from_numpy(label_x).to(device)
        label_y = torch.from_numpy(label_y).to(device)
        print(f'[GMM init] Kx={kx} Ky={ky}')

        model.train()
        for epoch in range(1, n_epochs_soft+1):
            loss, rec, sp, tx, ty, dgi = model.compute_losses(
                xb, yb, label_x, label_y,
                triplet_margin=margin_estimate,
                weight_penalty=lambda_regul,
                triplet_lambda=lambda_super,
                dgi_lambda=dgi_lambda,
                g_x=g_x,
                g_y=g_y
            )

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # 周期性刷新 GMM（在最新 h_x/h_y 上）
            if (epoch % gmm_update_every) == 0:
                with torch.no_grad():
                    _, _, _, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
                label_x, prob_x_np, kx = gmm_cluster(hx.detach().cpu().numpy(), k_range=k_range_x,
                                               covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                label_y, prob_y_np, ky = gmm_cluster(hy.detach().cpu().numpy(), k_range=k_range_y,
                                               covariance_type=gmm_covariance_type, reg_covar=gmm_reg_covar)
                label_x = torch.from_numpy(label_x).to(device)
                label_y = torch.from_numpy(label_y).to(device)
                if verbose:
                    print(f'  [GMM refresh] ep={epoch} Kx={kx} Ky={ky}')

            if verbose and (epoch % 50 == 0):
                print(f'[hard] ep={epoch:03d} loss={loss.item():.5f} rec={rec.item():.5f} '
                      f'sp={sp.item():.5f} tri_x={tx.item():.5f} tri_y={ty.item():.5f} dgi={dgi.item():.5f}')

    # ======== 推理输出：建议全图一次前向拿到完整嵌入与重构 ========
    model.eval()
    with torch.no_grad():
        z, xh, yh, hx, hy, _ = model(xb, yb, g_x=g_x, g_y=g_y)
        latent = z.detach().cpu().numpy()
        reconstruct_x = xh.detach().cpu().numpy()
        reconstruct_y = yh.detach().cpu().numpy()
        latent_x = hx.detach().cpu().numpy()
        latent_y = hy.detach().cpu().numpy()

    print('++++++++++ Model (PyTorch, full/subgraph) completed ++++++++++')
    return latent, reconstruct_x, reconstruct_y, latent_x, latent_y


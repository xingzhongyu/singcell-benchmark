import numpy as np
import pandas as pd
import phenograph
from matplotlib import pyplot as plt
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
import umap
import scanpy as sc
import ot
import os
from matplotlib.colors import ListedColormap
from sklearn.neighbors import NearestNeighbors
from utils import gmm_cluster_fixed_k, set_seed


def pick_long_palette(n_target: int):
    """返回长度>=n_target的颜色列表；优先用 scanpy 内置长色板。"""
    # 候选（按优先级排序；不同版本可用性不同）
    candidate_names = [
        "default_102",    # >=102（优先）
        "godsnot_102",    # 另一套长色板（有版本差异）
        "default_28",
        "zeileis_28",
        "vega_20_scanpy",
        "vega_20",
    ]
    colors = []
    for name in candidate_names:
        if hasattr(sc.pl.palettes, name):
            colors += list(getattr(sc.pl.palettes, name))
        if len(colors) >= n_target:
            return colors[:n_target]

    # 兜底：等分色环（区分度一般，但保证够长）
    colors = [plt.cm.hsv(i / n_target) for i in range(n_target)]
    # 转成 hex
    colors = [plt.matplotlib.colors.to_hex(c) for c in colors]
    return colors

def set_scanpy_colors_for_key(adata, key: str):
    """为分类变量 key 设置足够长且固定的颜色表，写入 adata.uns['<key>_colors']。"""
    if not pd.api.types.is_categorical_dtype(adata.obs[key]):
        adata.obs[key] = adata.obs[key].astype("category")
    cats = list(adata.obs[key].cat.categories)
    palette = pick_long_palette(len(cats))
    adata.uns[f"{key}_colors"] = palette

def scatter_with_scanpy_colors(ax, emb2d, labels, adata, key: str, title, s=6, alpha=0.8):
    """使用与 Scanpy 完全一致的类别顺序 + 颜色绘制散点。"""
    # 保证 uns 里已有颜色
    set_scanpy_colors_for_key(adata, key)
    cats = list(adata.obs[key].cat.categories)
    colors = adata.uns[f"{key}_colors"]
    # 将 labels 按同一 categories 编码成整数索引
    codes = pd.Categorical(labels, categories=cats, ordered=True).codes
    ax.scatter(emb2d[:, 0], emb2d[:, 1],
               c=codes, s=s, alpha=alpha,
               cmap=ListedColormap(colors), linewidths=0)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xticks([]); ax.set_yticks([])

def refine_label(adata, n_neighbors=50, key='label'):
    y = np.asarray(adata.obs[key])
    pos = adata.obsm['spatial']
    n_neighbors = min(n_neighbors, len(pos)-1)  # 防越界
    nn = NearestNeighbors(n_neighbors=n_neighbors+1, metric='euclidean').fit(pos)
    dists, idx = nn.kneighbors(pos, return_distance=True)  # idx[:,0] 是自己
    neigh_idx = idx[:, 1:]  # 去掉自己
    # 多数投票（ties 时取出现顺序最早的）
    new_type = []
    for row in neigh_idx:
        vals, counts = np.unique(y[row], return_counts=True)
        new_type.append(vals[np.argmax(counts)])
    return [str(v) for v in new_type]



def clustering_visualization(adata,
                                cluster_key_ct='cell_type_broad',
                                cluster_key_dom='topological_domain',
                                n_cell_type=None,
                                n_domains=None,
                                z=None,
                                z_x=None,
                                z_y=None,
                                k_pg=30,
                                s_scatter=6,
                                s_spatial=10,
                                refinement=True,
                                save_path=None
                             ):
    set_seed()

    if save_path is None:
        raise ValueError("save_path 不能为空")
    os.makedirs(save_path, exist_ok=True)

    # ## Perform final clustering
    z_label, _, _ = phenograph.cluster(z, k=k_pg, n_jobs=1, clustering_algo='leiden')
    z_x_label, _, _ = gmm_cluster_fixed_k(z_x, n_cell_type)
    z_y_label, _, _ = gmm_cluster_fixed_k(z_y, n_domains)

    adata.obs["z_x_cluster"] = pd.Series(z_x_label, index=adata.obs_names).astype("category")  # 转成字符串，scanpy画图时更稳
    adata.obs["z_y_cluster"] = pd.Series(z_y_label, index=adata.obs_names).astype("category")
    adata.obs["z_joint_cluster"] = pd.Series(z_label, index=adata.obs_names).astype("category")

    if refinement:
        adata.obs['z_x_cluster'] = pd.Series(refine_label(adata, n_neighbors=50, key='z_x_cluster'),
                                             index=adata.obs_names).astype("category")
        adata.obs['z_y_cluster'] = pd.Series(refine_label(adata, n_neighbors=50, key='z_y_cluster'),
                                             index=adata.obs_names).astype("category")
        adata.obs['z_joint_cluster'] = pd.Series(refine_label(adata, n_neighbors=50, key='z_joint_cluster'),
                                                 index=adata.obs_names).astype("category")

    # 细化后再统一刷新一次颜色表（可选）
    for key in ["z_x_cluster", "z_y_cluster", "z_joint_cluster"]:
        set_scanpy_colors_for_key(adata, key)  # 如果颜色已存在且长度匹配，会原样返回

    # ## Visualization and quantification using UMAP
    # label_true_ct = np.asarray(adata.obs[cluster_key_ct])
    # label_true_domain = np.asarray(adata.obs[cluster_key_dom])

    # 统一的 UMAP 配置（可根据需要调整）
    umap_cfg = dict(n_components=2, n_neighbors=30, min_dist=0.3, metric="euclidean", random_state=0)

    # 各自只 fit 一次
    umap_x = umap.UMAP(**umap_cfg).fit_transform(z_x)  # transcript-alone
    umap_y = umap.UMAP(**umap_cfg).fit_transform(z_y)  # spatial-neighbor-alone
    umap_z = umap.UMAP(**umap_cfg).fit_transform(z)  # joint latent

    # 计算 ARI（对齐逻辑：z_x↔CT，z_y↔Domain，z↔{Domain, CT}）
    ari_x_vs_ct = adjusted_rand_score(adata.obs[cluster_key_ct], adata.obs['z_x_cluster'])
    ari_y_vs_dom = adjusted_rand_score(adata.obs[cluster_key_dom], adata.obs['z_y_cluster'])
    ari_z_vs_ct = adjusted_rand_score(adata.obs[cluster_key_ct], adata.obs['z_joint_cluster'])
    ari_z_vs_dom = adjusted_rand_score(adata.obs[cluster_key_dom], adata.obs['z_joint_cluster'])


    # 计算 NMI（对齐逻辑：z_x↔CT，z_y↔Domain，z↔{Domain, CT}）
    nmi_x_vs_ct = normalized_mutual_info_score(adata.obs[cluster_key_ct], adata.obs['z_x_cluster'])
    nmi_y_vs_dom = normalized_mutual_info_score(adata.obs[cluster_key_dom], adata.obs['z_y_cluster'])
    nmi_z_vs_ct = normalized_mutual_info_score(adata.obs[cluster_key_ct], adata.obs['z_joint_cluster'])
    nmi_z_vs_dom = normalized_mutual_info_score(adata.obs[cluster_key_dom], adata.obs['z_joint_cluster'])


    # ## UMAP visualization
    z_x_label = np.asarray(adata.obs['z_x_cluster'])
    z_y_label = np.asarray(adata.obs['z_y_cluster'])
    z_label = np.asarray(adata.obs['z_joint_cluster'])
    fig1, axes = plt.subplots(1, 4, figsize=(18, 5), constrained_layout=True)
    # 1) z_x vs cell_type_broad
    # scatter_by_label(
    #     axes[0], umap_x, z_x_label, s=s_scatter,
    #     title = f"Transcript-alone (vs CT)\nNMI={nmi_x_vs_ct:0.3f}, ARI={ari_x_vs_ct:0.3f}"
    # )
    scatter_with_scanpy_colors(
        axes[0], umap_x, z_x_label, adata, key="z_x_cluster",
        title=f"Transcript-alone (vs CT)\nNMI={nmi_x_vs_ct:0.3f}, ARI={ari_x_vs_ct:0.3f}",
        s=s_scatter
    )
    # 2) z_y vs topological_domain
    # scatter_by_label(
    #     axes[1], umap_y, z_y_label, s=s_scatter,
    #     title = f"Spatial-alone (vs Domain)\nNMI={nmi_y_vs_dom:0.3f}, ARI={ari_y_vs_dom:0.3f}"
    # )
    scatter_with_scanpy_colors(
        axes[1], umap_y, z_y_label, adata, key="z_y_cluster",
        title=f"Spatial-alone (vs Domain)\nNMI={nmi_y_vs_dom:0.3f}, ARI={ari_y_vs_dom:0.3f}",
        s=s_scatter
    )
    # 3) z vs cell_type_broad
    # scatter_by_label(
    #     axes[2], umap_z, z_label, s=s_scatter,
    #     title = f"Joint latent (vs CT)\nNMI={nmi_z_vs_ct:0.3f}, ARI={ari_z_vs_ct:0.3f}"
    # )
    scatter_with_scanpy_colors(
        axes[2], umap_z, z_label, adata, key="z_joint_cluster",
        title=f"Joint latent (vs CT)\nNMI={nmi_z_vs_ct:0.3f}, ARI={ari_z_vs_ct:0.3f}",
        s=s_scatter
    )
    # 4) z vs topological_domain
    # scatter_by_label(
    #     axes[3], umap_z, z_label, s=s_scatter,
    #     title = f"Joint latent (vs Domain)\nNMI={nmi_z_vs_dom:0.3f}, ARI={ari_z_vs_dom:0.3f}"
    # )
    scatter_with_scanpy_colors(
        axes[3], umap_z, z_label, adata, key="z_joint_cluster",
        title=f"Joint latent (vs Domain)\nNMI={nmi_z_vs_dom:0.3f}, ARI={ari_z_vs_dom:0.3f}",
        s=s_scatter
    )
    fig1.savefig(f"{save_path}/transcript_spatial_joint.png", bbox_inches='tight', dpi=300)
    plt.show()

    # ## spatial visualization
    # --- First Figure: Transcript-alone ---
    fig1, ax1 = plt.subplots(figsize=(6, 5))  # Adjust figsize as needed
    sc.pl.embedding(
        adata,
        basis="spatial",
        color="z_x_cluster",
        s=s_spatial,
        show=False,
        ax=ax1
    )
    title1 = f"Transcript-alone (vs CT)\nNMI={nmi_x_vs_ct:0.3f}, ARI={ari_x_vs_ct:0.3f}"
    ax1.set_title(title1, fontsize=14, fontweight='bold')  # Set fontsize and bold
    ax1.set_axis_off()  # Turn off the axis
    fig1.savefig(f"{save_path}/transcript_alone.png", bbox_inches='tight',dpi=300)
    plt.show()

    # --- Second Figure: Spatial-alone ---
    fig2, ax2 = plt.subplots(figsize=(6, 5))
    sc.pl.embedding(
        adata,
        basis="spatial",
        color="z_y_cluster",
        s=s_spatial,
        show=False,
        ax=ax2
    )
    title2 = f"Spatial-alone (vs Domain)\nNMI={nmi_y_vs_dom:0.3f}, ARI={ari_y_vs_dom:0.3f}"
    ax2.set_title(title2, fontsize=14, fontweight='bold')
    ax2.set_axis_off()
    fig2.savefig(f"{save_path}/spatial_alone.png", bbox_inches='tight', dpi=300)
    plt.show()

    # --- Third Figure: Joint latent ---
    fig3, ax3 = plt.subplots(figsize=(6, 5))
    sc.pl.embedding(
        adata,
        basis="spatial",
        color="z_joint_cluster",
        s=s_spatial,
        show=False,
        ax=ax3
    )
    title3 = "Joint latent"
    ax3.set_title(title3, fontsize=14, fontweight='bold')
    ax3.set_axis_off()
    fig3.savefig(f"{save_path}/joint_latent.png", bbox_inches='tight', dpi=300)
    plt.show()

    return adata, ari_x_vs_ct, ari_y_vs_dom, ari_z_vs_ct, ari_z_vs_dom, nmi_x_vs_ct, nmi_y_vs_dom, nmi_z_vs_ct, nmi_z_vs_dom
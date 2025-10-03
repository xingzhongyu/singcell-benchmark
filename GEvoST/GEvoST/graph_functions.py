import numpy as np
import scipy.sparse as sp
from sklearn.neighbors import kneighbors_graph, NearestNeighbors
from scipy.spatial import Delaunay
import dgl

def _print_undirected_edge_count(g: dgl.DGLGraph, prefix: str = ""):
    n = g.num_nodes()
    E = g.num_edges()
    # 每个节点 1 个自环；无向=双向，所以要扣掉自环再除以 2
    undirected = (E - n) // 2
    print(f"{prefix}（{n} 节点，对称边数 {undirected}，含自环）")

def features_construct_graph(adata, k=3, pca=None, mode="connectivity", metric="cosine"):
    """
    用特征 KNN 构图 → 二值化 → 对称化 → 单自环
    适用于无权重 GCN
    """
    X = adata.X if pca is None else dopca(adata.X, dim=pca)

    # 先不带自环构 KNN（后面统一用 dgl.add_self_loop 处理）
    A = kneighbors_graph(
        X, k + 1, mode=mode, metric=metric, include_self=False
    ).tocsr()                               # 稀疏 KNN 图
    if mode != "connectivity":
        # 无权 GCN：对称二值化；距离/相似度都只保留“有/无”
        A.data[:] = 1.0

    # 对称二值化：无向 = A∪A^T
    A_sym = (A + A.T).sign().tocsr()

    # 用 scipy 构图，再统一“先去再加”自环，确保每个节点恰好 1 个自环
    g_sym = dgl.from_scipy(A_sym)
    g_sym = dgl.remove_self_loop(g_sym)
    g_sym = dgl.add_self_loop(g_sym)

    # 非对称图可直接在需要时再建；GCN 只用对称图即可
    print("✅ 特征图构建完成", end='')
    _print_undirected_edge_count(g_sym)
    return g_sym, None  # 若仍想返回非对称图，可按需构造


def construct_interaction_KNN(adata, n_neighbors=3):
    pos = adata.obsm['spatial']
    n = pos.shape[0]

    nbrs = NearestNeighbors(n_neighbors=n_neighbors + 1).fit(pos)
    _, indices = nbrs.kneighbors(pos)

    src = np.repeat(np.arange(n), n_neighbors)
    dst = indices[:, 1:].reshape(-1)

    # 对称（双向）+ 单自环
    src_sym = np.concatenate([src, dst])
    dst_sym = np.concatenate([dst, src])
    g_sym = dgl.graph((src_sym, dst_sym), num_nodes=n)
    g_sym = dgl.remove_self_loop(g_sym)
    g_sym = dgl.add_self_loop(g_sym)

    print("✅ 空间 KNN 图构建完成", end='')
    _print_undirected_edge_count(g_sym)
    return g_sym, None


def construct_delaunay(adata, spatial_key='spatial', percentile=90):
    pos = adata.obsm[spatial_key]
    n = pos.shape[0]

    tri = Delaunay(pos)
    undirected = set()
    for a, b, c in tri.simplices:
        for u, v in ((a, b), (b, c), (c, a)):
            i, j = (u, v) if u < v else (v, u)
            undirected.add((i, j))

    edges = np.array(list(undirected), dtype=int)  # (M, 2)
    # 剪枝：保留最短的 p% 边
    d = np.linalg.norm(pos[edges[:,0]] - pos[edges[:,1]], axis=1)
    thr = np.percentile(d, percentile)
    keep = edges[d <= thr]

    # 双向边 + 单自环
    src_sym = np.concatenate([keep[:,0], keep[:,1]])
    dst_sym = np.concatenate([keep[:,1], keep[:,0]])
    g_sym = dgl.graph((src_sym, dst_sym), num_nodes=n)
    g_sym = dgl.remove_self_loop(g_sym)
    g_sym = dgl.add_self_loop(g_sym)

    print(f"📐 Delaunay 剪枝阈值 = {thr:.4f}")
    print("✅ Delaunay 图构建完成", end='')
    _print_undirected_edge_count(g_sym)
    return g_sym, None

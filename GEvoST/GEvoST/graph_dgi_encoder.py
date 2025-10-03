# 新增：graph_dgi_encoder.py
import torch, dgl
import torch.nn as nn
import torch.nn.functional as F
import dgl.nn as dglnn

class GCNEncoder(nn.Module):
    """简单两层 GCN，可替换成 GIN/SAGE 等"""
    def __init__(self, in_dim: int, hidden_dim: int, num_layers: int = 2):
        super().__init__()
        dims = [in_dim] + [hidden_dim] * num_layers
        self.layers = nn.ModuleList([dglnn.GraphConv(dims[i], dims[i+1], allow_zero_in_degree=True)
                                     for i in range(num_layers)])
        self.act = nn.PReLU()

    def forward(self, g: dgl.DGLGraph, x: torch.Tensor) -> torch.Tensor:
        h = x
        for conv in self.layers:
            h = conv(g, h)
            h = self.act(h)
        return h

class DGIHead(nn.Module):
    """DGI 判别头：对比(真实节点嵌入, 图摘要) vs (扰动节点嵌入, 图摘要)"""
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.disc = nn.Bilinear(hidden_dim, hidden_dim, 1)

    @staticmethod
    def _summary(g: dgl.DGLGraph, h: torch.Tensor) -> torch.Tensor:
        # 图级摘要 s：每个子图/批内图的节点均值再过 sigmoid
        g = g.local_var()
        g.ndata['h'] = h
        s = dgl.mean_nodes(g, 'h')               # [B, hidden] (B=批内图个数; 单图时 B=1)
        s = torch.sigmoid(s)
        return s

    @staticmethod
    def _expand_summary_to_nodes(g: dgl.DGLGraph, s: torch.Tensor) -> torch.Tensor:
        # 把每个图的摘要 s[b] 复制到该图的所有节点上（处理 batched graphs）
        if g.batch_size is None:  # 单图
            return s.expand(g.num_nodes(), -1)
        counts = g.batch_num_nodes().tolist()
        idx = torch.arange(len(counts), device=s.device).repeat_interleave(torch.tensor(counts, device=s.device))
        return s.index_select(0, idx)            # [sum_nodes, hidden]

    def loss(self, g: dgl.DGLGraph, h: torch.Tensor, h_corrupt: torch.Tensor) -> torch.Tensor:
        s = self._summary(g, h)                  # [B, H]
        s_nodes = self._expand_summary_to_nodes(g, s)  # [N, H]

        pos = self.disc(h, s_nodes).squeeze(-1)       # [N]
        neg = self.disc(h_corrupt, s_nodes).squeeze(-1)
        bce = nn.BCEWithLogitsLoss()
        loss = bce(pos, torch.ones_like(pos)) + bce(neg, torch.zeros_like(neg))
        return loss

class EncoderDGI(nn.Module):
    """替换原 MLP 的图编码器：返回节点嵌入与 DGI 自监督损失"""
    def __init__(self, in_dim: int, hidden_dim: int, num_layers: int = 2, corruption: str = 'permute'):
        super().__init__()
        self.gnn = GCNEncoder(in_dim, hidden_dim, num_layers)
        self.head = DGIHead(hidden_dim)
        self.corruption = corruption

    def _corrupt(self, x: torch.Tensor) -> torch.Tensor:
        if self.corruption == 'permute':
            return x[torch.randperm(x.size(0), device=x.device)]
        elif self.corruption == 'gaussian':
            return x + 0.1 * torch.randn_like(x)
        else:
            raise ValueError(f'Unknown corruption: {self.corruption}')

    def forward(self, g: dgl.DGLGraph, x: torch.Tensor, return_dgi_loss: bool = True):
        h = self.gnn(g, x)                        # 节点嵌入 [N, hidden]
        loss_dgi = None
        if return_dgi_loss:
            x_tilde = self._corrupt(x)
            h_tilde = self.gnn(g, x_tilde)
            loss_dgi = self.head.loss(g, h, h_tilde)
        return h, loss_dgi

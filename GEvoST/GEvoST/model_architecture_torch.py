# 修改：muse_architecture_torch.py
import torch
import torch.nn as nn
from triplet_loss_torch import batch_hard_triplet_loss
from graph_dgi_encoder import EncoderDGI  # ← 新增导入

class Decoder(nn.Module):
    def __init__(self, in_dim: int, n_hidden: int, out_dim: int):
        super().__init__()
        self.w0 = nn.Linear(in_dim, n_hidden)
        self.w1 = nn.Linear(n_hidden, n_hidden)
        self.wo = nn.Linear(n_hidden, out_dim)
        self.elu = nn.ELU()
    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return self.wo(torch.tanh(self.w1(self.elu(self.w0(z)))))

class Model(nn.Module):
    """
    支持两种编码器：'mlp'（旧）与 'dgi'（新，DGL 图编码）
    """
    def __init__(self, dim_x: int, dim_y: int, n_hidden: int, dim_z: int,
                 encoder_type: str = 'dgi', gnn_layers: int = 2):
        super().__init__()
        self.encoder_type = encoder_type
        if encoder_type == 'dgi':
            self.enc_x = EncoderDGI(dim_x, n_hidden, num_layers=gnn_layers)
            self.enc_y = EncoderDGI(dim_y, n_hidden, num_layers=gnn_layers)
        else:
            # 兼容：保留原 MLP 编码器
            self.w0x = nn.Linear(dim_x, n_hidden); self.w1x = nn.Linear(n_hidden, n_hidden)
            self.w0y = nn.Linear(dim_y, n_hidden); self.w1y = nn.Linear(n_hidden, n_hidden)
            self.elu = nn.ELU()

        self.wo = nn.Linear(2 * n_hidden, dim_z, bias=True)
        self.w_selection_x = nn.Parameter(torch.randn(dim_z, dim_z))
        self.w_selection_y = nn.Parameter(torch.randn(dim_z, dim_z))
        self.dec_x = Decoder(dim_z, n_hidden, dim_x)
        self.dec_y = Decoder(dim_z, n_hidden, dim_y)

    def _encode(self, x, y, g_x=None, g_y=None):
        if self.encoder_type == 'dgi':
            assert g_x is not None and g_y is not None, "DGI 编码器需要传入 DGL 图 g_x/g_y"
            h_x, dgi_x = self.enc_x(g_x, x, return_dgi_loss=True)
            h_y, dgi_y = self.enc_y(g_y, y, return_dgi_loss=True)
            dgi_loss = dgi_x + dgi_y
        else:
            # 原 MLP：ELU→tanh
            hx0 = self.elu(self.w0x(x)); h_x = torch.tanh(self.w1x(hx0))
            hy0 = self.elu(self.w0y(y)); h_y = torch.tanh(self.w1y(hy0))
            dgi_loss = torch.tensor(0., device=h_x.device)
        return h_x, h_y, dgi_loss

    def forward(self, x: torch.Tensor, y: torch.Tensor, g_x=None, g_y=None):
        h_x, h_y, dgi_loss = self._encode(x, y, g_x, g_y)
        h = torch.cat([h_x, h_y], dim=1)
        z = self.wo(h)
        x_hat = self.dec_x(z @ self.w_selection_x)
        y_hat = self.dec_y(z @ self.w_selection_y)
        return z, x_hat, y_hat, h_x, h_y, dgi_loss

    def compute_losses(self, x, y, label_x, label_y,
                       triplet_margin: float, weight_penalty: float,
                       triplet_lambda: float, dgi_lambda: float = 0.0,
                       g_x=None, g_y=None):
        """
        新增 dgi_lambda 与 g_x/g_y；其余保持兼容
        """
        z, x_hat, y_hat, h_x, h_y, dgi_loss = self.forward(x, y, g_x, g_y)

        # reconstruction（与原版一致）
        x_mask = (x.sign() != 0).float()
        num_nonzero = torch.clamp(x_mask.sum(), min=1.0)
        reconstruct_x = torch.norm(x_mask * (x_hat - x)) / num_nonzero
        reconstruct_y = torch.norm(y_hat - y)
        reconstruct_loss = reconstruct_x + reconstruct_y

        # "sparse" penalty
        sparse_penalty = torch.norm(self.w_selection_x, p='fro') + torch.norm(self.w_selection_y, p='fro')

        # triplet（联合潜空间 z 上）
        label_x = label_x.long(); label_y = label_y.long()
        trip_loss_x = batch_hard_triplet_loss(label_x, z, triplet_margin)
        trip_loss_y = batch_hard_triplet_loss(label_y, z, triplet_margin)

        loss = (reconstruct_loss
                + weight_penalty * sparse_penalty
                + triplet_lambda * (trip_loss_x + trip_loss_y)
                + dgi_lambda * dgi_loss)

        return loss, reconstruct_loss, sparse_penalty, trip_loss_x, trip_loss_y, dgi_loss

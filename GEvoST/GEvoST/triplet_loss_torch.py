
import torch

def _pairwise_distances(embeddings: torch.Tensor, squared: bool = False) -> torch.Tensor:
    """
    Compute the 2D matrix of pairwise distances between embeddings.
    Args:
        embeddings: (batch_size, embed_dim)
        squared: if True return squared Euclidean distances
    Returns:
        distances: (batch_size, batch_size)
    """
    # ||a - b||^2 = ||a||^2 - 2<a, b> + ||b||^2
    dot_product = embeddings @ embeddings.t()
    square_norm = torch.diagonal(dot_product, 0)

    distances = square_norm.unsqueeze(1) - 2.0 * dot_product + square_norm.unsqueeze(0)
    distances = torch.clamp(distances, min=0.0)

    if not squared:
        # add small epsilon for numerical stability where distance == 0
        mask = (distances == 0.0).float()
        distances = distances + mask * 1e-16
        distances = torch.sqrt(distances)
        distances = distances * (1.0 - mask)

    return distances


def _get_anchor_positive_triplet_mask(labels: torch.Tensor) -> torch.Tensor:
    """
    Return a 2D mask [a, p] True iff a and p are distinct and have same label.
    labels: (batch_size,)
    """
    batch_size = labels.size(0)
    indices_equal = torch.eye(batch_size, dtype=torch.bool, device=labels.device)
    indices_not_equal = ~indices_equal

    labels_equal = labels.unsqueeze(0) == labels.unsqueeze(1)
    mask = indices_not_equal & labels_equal
    return mask


def _get_anchor_negative_triplet_mask(labels: torch.Tensor) -> torch.Tensor:
    """
    Return a 2D mask [a, n] True iff a and n have distinct labels.
    labels: (batch_size,)
    """
    labels_equal = labels.unsqueeze(0) == labels.unsqueeze(1)
    return ~labels_equal


def _get_triplet_mask(labels: torch.Tensor) -> torch.Tensor:
    """
    Return a 3D mask [a, p, n] True iff the triplet (a, p, n) is valid.
    Valid if:
      - a, p, n are distinct
      - labels[a] == labels[p] and labels[a] != labels[n]
    """
    batch_size = labels.size(0)
    indices_equal = torch.eye(batch_size, dtype=torch.bool, device=labels.device)
    indices_not_equal = ~indices_equal
    i_not_equal_j = indices_not_equal.unsqueeze(2)
    i_not_equal_k = indices_not_equal.unsqueeze(1)
    j_not_equal_k = indices_not_equal.unsqueeze(0)
    distinct_indices = i_not_equal_j & i_not_equal_k & j_not_equal_k

    label_equal = labels.unsqueeze(0) == labels.unsqueeze(1)
    i_equal_j = label_equal.unsqueeze(2)
    i_equal_k = label_equal.unsqueeze(1)
    valid_labels = i_equal_j & (~i_equal_k)

    mask = distinct_indices & valid_labels
    return mask


def batch_all_triplet_loss(labels: torch.Tensor,
                           embeddings: torch.Tensor,
                           margin: float,
                           squared: bool = False) -> torch.Tensor:
    """
    Build the triplet loss over a batch of embeddings by enumerating all valid triplets.
    Returns scalar loss.
    """
    pairwise_dist = _pairwise_distances(embeddings, squared=squared)
    anchor_positive_dist = pairwise_dist.unsqueeze(2)   # (B,B,1)
    anchor_negative_dist = pairwise_dist.unsqueeze(1)   # (B,1,B)

    triplet_loss = anchor_positive_dist - anchor_negative_dist + margin
    mask = _get_triplet_mask(labels).float()
    triplet_loss = mask * triplet_loss
    triplet_loss = torch.clamp(triplet_loss, min=0.0)

    valid_triplets = (triplet_loss > 1e-16).float()
    num_positive_triplets = torch.sum(valid_triplets)
    # Avoid division by zero
    triplet_loss = torch.sum(triplet_loss) / (num_positive_triplets + 1e-16)

    return triplet_loss


def batch_hard_triplet_loss(labels: torch.Tensor,
                            embeddings: torch.Tensor,
                            margin: float,
                            squared: bool = False) -> torch.Tensor:
    """
    Build the triplet loss over a batch of embeddings by using
    hardest positive and hardest negative for each anchor.
    """
    pairwise_dist = _pairwise_distances(embeddings, squared=squared)

    # Hardest positive: for each anchor, the maximum distance to any positive
    mask_anchor_positive = _get_anchor_positive_triplet_mask(labels).float()
    anchor_positive_dist = mask_anchor_positive * pairwise_dist
    hardest_positive_dist, _ = anchor_positive_dist.max(dim=1, keepdim=True)

    # Hardest negative: for each anchor, the minimum distance to any negative
    mask_anchor_negative = _get_anchor_negative_triplet_mask(labels).float()
    max_anchor_negative_dist, _ = pairwise_dist.max(dim=1, keepdim=True)
    anchor_negative_dist = pairwise_dist + max_anchor_negative_dist * (1.0 - mask_anchor_negative)
    hardest_negative_dist, _ = anchor_negative_dist.min(dim=1, keepdim=True)

    loss = torch.clamp(hardest_positive_dist - hardest_negative_dist + margin, min=0.0)
    loss = loss.mean()
    return loss


# ---------- 工具：软三元组 ----------
import torch

def __pairwise_distances(emb: torch.Tensor, squared: bool = False) -> torch.Tensor:
    # 高效 pairwise 欧式距离（B,B）
    dot = emb @ emb.t()
    sq = torch.diag(dot)
    dist = sq.unsqueeze(1) - 2.0*dot + sq.unsqueeze(0)
    dist = torch.clamp(dist, min=0.0)
    if not squared:
        z = (dist == 0.0).float()
        dist = torch.sqrt(dist + z*1e-16) * (1.0 - z)
    return dist

def _soft_triplet_one_view_sampled(D: torch.Tensor, P: torch.Tensor, margin: float,
                                   top_pos: int = 8, top_neg: int = 16) -> torch.Tensor:
    """
    D: (B,B) pairwise distance
    P: (B,B) soft co-membership affinity（如 probs @ probs.T，已截断到 [0,1]）
    仅保留每个 anchor 的 top-P 正、top-N 负，复杂度 ~ B*P*N
    """
    B = D.size(0)
    dev = D.device
    eye = torch.eye(B, device=dev, dtype=D.dtype)

    S = torch.clamp(P, 0.0, 1.0)
    Pos = S * (1.0 - eye)         # 去掉自己
    Neg = (1.0 - S) * (1.0 - eye)

    # 每行 top-K 索引
    pos_scores, pos_idx = Pos.topk(k=min(top_pos, B-1), dim=1, largest=True, sorted=False)     # (B,P)
    neg_scores, neg_idx = Neg.topk(k=min(top_neg, B-1), dim=1, largest=True, sorted=False)     # (B,N)

    ar = torch.arange(B, device=dev).unsqueeze(1)                                              # (B,1)
    D_pos = D[ar, pos_idx]        # (B,P)
    D_neg = D[ar, neg_idx]        # (B,N)

    # 权重：w_ijk = S_ij * (1 - S_ik)（分别 gather 到子集上）
    Wpos = pos_scores             # (B,P) = S_ij
    Wneg = neg_scores             # (B,N) = 1 - S_ik

    # 广播到 (B,P,N)，但 P*N 很小（例如 8*16）
    T = torch.relu(D_pos.unsqueeze(2) - D_neg.unsqueeze(1) + margin)  # (B,P,N)
    W = Wpos.unsqueeze(2) * Wneg.unsqueeze(1)                          # (B,P,N)

    loss = (W * T).sum()
    denom = W.sum() + 1e-16
    return loss / denom

def soft_triplet_batch_all_sampled(z: torch.Tensor,
                                   probs_x: torch.Tensor,
                                   probs_y: torch.Tensor,
                                   margin: float,
                                   top_pos: int = 8,
                                   top_neg: int = 16) -> torch.Tensor:
    """
    采样版软三元组：对两路分别计算后取平均
    """
    D = _pairwise_distances(z)                          # (B,B)
    Sx = torch.clamp(probs_x @ probs_x.t(), 0.0, 1.0)  # (B,B)
    Sy = torch.clamp(probs_y @ probs_y.t(), 0.0, 1.0)

    lx = _soft_triplet_one_view_sampled(D, Sx, margin, top_pos, top_neg)
    ly = _soft_triplet_one_view_sampled(D, Sy, margin, top_pos, top_neg)
    return 0.5 * (lx + ly)


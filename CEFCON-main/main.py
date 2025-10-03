
##-------------------------只推断谱系特异性GRN-------------------
import numpy as np
import cefcon as cf
import matplotlib.pyplot as plt
import scanpy as sc
import pandas as pd
import warnings
warnings.filterwarnings("ignore")
## 加载数据
# adata = cf.datasets.mouse_hsc_nestorowa16()
# adata

## 读取表达数据
df = pd.read_csv("./input/mesc2/total_m2_expression.csv",index_col=0)
print(df)
#df_gene = pd.read_csv("gene_index1000.csv")
#gene_list1 = list(df_gene["gene"].values)
#gene_list = [i.lower() for i in gene_list1]

#df_data = df.loc[gene_list]
df.index = df.index.str.upper()
df_data = df
print(df_data)

from anndata import AnnData
# 创建一个空的AnnData对象
# 创建 AnnData 对象
adata = AnnData(df_data.values.T,dtype=np.float32)  # 转置是因为 AnnData 的行是样本/细胞，列是特征/基因

# 设置行索引（细胞名称）
adata.obs_names = df_data.columns

# 设置列索引（基因名称）
adata.var_names = df_data.index

print(adata)

adata.obs_names = df_data.columns
adata.var_names = df_data.index

# Normalization
sc.pp.normalize_total(adata, target_sum=1e4)
# Log transformation
sc.pp.log1p(adata)
adata.X = adata.X.astype(np.float32)
adata.layers['log_transformed'] = adata.X.copy()




prior_network = cf.datasets.load_human_prior_interaction_network(dataset='nichenet')
# # Convert the gene symbols of the prior gene interaction network to the mouse gene symbols
prior_network = cf.datasets.convert_human_to_mouse_network(prior_network)
print(prior_network)
data = cf.data_preparation(adata, prior_network)

# cefcon_results_dict = {}
# for li, data_li in data.items():
#     # We suggest setting up multiple repeats to minimize the randomness of the computation.
#     cefcon_GRN_model = cf.NetModel(epochs=250, repeats=1, seed=-1)
#     cefcon_GRN_model.run(data_li)
#     cefcon_results = cefcon_GRN_model.get_cefcon_results(edge_threshold_avgDegree=8)
#     cefcon_results_dict[li] = cefcon_results

cefcon_GRN_model = cf.NetModel(epochs=250, repeats=1, seed=-1)
cefcon_GRN_model.run(data['all']) ## 只有一个浦西

#
from os import fspath
from pathlib import Path
p = Path("./output/mesc2")
if not p.exists():
    Path.mkdir(p)

G_predicted = cefcon_GRN_model.get_network(edge_threshold_avgDegree=None,edge_threshold_zscore=None,output_file=fspath(p / 'cell_lineage_GRN.csv'))

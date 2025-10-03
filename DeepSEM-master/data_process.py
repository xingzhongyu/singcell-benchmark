##-----------------将数据转换成该模型需要的格式------------------------
# import pandas as pd
# data = pd.read_csv('./demo_data/GRN_inference/input/mesc2/total_m2_expression.csv',index_col=0)
# data = data.T
# print(data)
# gene_name = data.columns.values
# print(gene_name)
# data.to_csv('./demo_data/GRN_inference/input/mesc2/data.csv')
#
# label = pd.read_csv('./demo_data/GRN_inference/input/mesc2/raw_label.csv')
# print(label)
#
# # for index,row in label.iterrows():
# #     row['TF'] = gene_name[row['TF']]
# #     row['Target'] = gene_name[row['Target']]
#
# col1 = []
# col2 = []
# for i in label['TF'].values:
#     col1.append(gene_name[i])
#
# for i in label['Target'].values:
#     col2.append(gene_name[i])
#
# c = {'Gene1':col1,'Gene2':col2}
# label = pd.DataFrame(c)
# label.to_csv('./demo_data/GRN_inference/input/mesc2/label.csv',index=False)
# print(label)

##-------------生成预测得分和真实得分，然后做评估--------------------------

import pandas as pd

raw_pre = pd.read_csv('./result/mesc2/GRN_inference_result.tsv',sep='\t')
raw_pre = raw_pre.dropna()
print(raw_pre.head())
data = pd.read_csv('./demo_data/GRN_inference/input/mesc2/total_m2_expression.csv',index_col=0)
data = data.T
print(data)
gene_name = list(data.columns.values)
print(gene_name)

col1 = []
col2 = []
col3 = []

for i in raw_pre['TF'].values:
    # 取索引，存col
    col1.append(gene_name.index(i))

for i in raw_pre['Target'].values:
    # 取索引，存col
    #print(i)
    col2.append(gene_name.index(i))

for i in raw_pre['EdgeWeight'].values:
    # 取索引，存col
    col3.append(abs(i))

c = {'Gene1':col1,'Gene2':col2,'weight':col3}
GRN_inference = pd.DataFrame(c)
GRN_inference.to_csv('./result/mesc2/GRN_inference.csv',index=False,header=None)
print(GRN_inference)

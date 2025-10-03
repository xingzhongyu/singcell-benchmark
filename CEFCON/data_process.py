import pandas as pd

df_target = pd.read_csv("./input/mHSC-L/Target.csv")
df_grn = pd.read_csv('./output/mHSC-L/cell_lineage_GRN.csv',header=None)
gene_index1 = list(df_target['Gene'].values)
gene_index = [j.upper() for j in gene_index1]
print(gene_index)
dic = {}
for i in gene_index:
    dic[i] = gene_index.index(i)
print(dic)


## 预处理下df_grn，去除不在dic[i]的
# 创建一个空列表，用于存储要删除的行索引
rows_to_delete = []

# 遍历DataFrame的每一行
for index, row in df_grn.iterrows():
    i, j, k = row[0], row[1], row[2]
    # 进行字典查询并捕获KeyError
    try:
        dic[i]
        dic[j]

    except KeyError:
        # 如果任意一个键错误，将当前行索引添加到要删除的行索引列表中
        rows_to_delete.append(index)

# 根据要删除的行索引，使用drop方法删除行
df_cleaned = df_grn.drop(rows_to_delete)
df_grn = df_cleaned
# 打印清理后的DataFrame
print("清理后的DataFrame:{}".format(df_grn))

c1 = []
c2 = []
c3 = []

for i in df_grn.iloc[:,0].tolist():
    try:
        c1.append(dic[i])
    except KeyError:
        continue

for i in df_grn.iloc[:,1].tolist():
    c2.append(dic[i])

for i in df_grn.iloc[:,2].tolist():
    c3.append(i)

c = {'TF':c1,'Gene':c2,'Weight':c3}
df_result = pd.DataFrame(c)
print(df_result)
df_result.to_csv('./output/mHSC-L/predicted_GRN.csv',index=False,header=None)
# from sklearn.metrics import average_precision_score
# import numpy as np
# import pandas as pd
#
# output = pd.read_csv('./result/mHSC-E/GRN_inference_result.tsv',sep='\t')
# output['EdgeWeight'] = abs(output['EdgeWeight']) ## 取正值，这个权重是代表相互作用的概率嘛？
# output = output.sort_values('EdgeWeight',ascending=False)
# label = pd.read_csv('./demo_data/GRN_inference/input/mHSC-E/label.csv')
# TFs = set(label['Gene1'])
# Genes = set(label['Gene1'])| set(label['Gene2'])
# output = output[output['TF'].apply(lambda x: x in TFs)]
# output = output[output['Target'].apply(lambda x: x in Genes)]
# label_set = set(label['Gene1']+label['Gene2'])
# preds,labels,randoms = [] ,[],[]
# res_d = {}
# l = []
# p= []
# for item in (output.to_dict('records')):
#         res_d[item['TF']+item['Target']] = item['EdgeWeight'] # 把推断的GRN里面的基因对的weight放里面
# for item in (set(label['Gene1'])):                        ## 对于每个TF，遍历所有基因，一共有TF*gene个对，看哪个基因对在label文件里
#         for item2 in  set(label['Gene1'])| set(label['Gene2']):
#             if item+item2 in label_set:
#                 print(item+item2)
#                 l.append(1)
#             else:
#                 l.append(0)
#             if item+ item2 in res_d:
#                 p.append(res_d[item+item2])
#             else:
#                 p.append(-1)
# print(average_precision_score(l,p)/np.mean(l))
# -------------------------------------------------------------------------


import pandas as pd
from sklearn.metrics import roc_auc_score,average_precision_score
import numpy as np
import torch

def Evaluation(y_true, y_pred,flag=False):
    if flag:
        # y_p = torch.argmax(y_pred,dim=1)
        y_p = y_pred[:,-1]
        y_p = y_p.cpu().detach().numpy()
        y_p = y_p.flatten()
    else:
        y_p = y_pred.cpu().detach().numpy()
        y_p = y_p.flatten()


    y_t = y_true.cpu().numpy().flatten().astype(int)

    AUC = roc_auc_score(y_true=y_t, y_score=y_p)


    AUPR = average_precision_score(y_true=y_t,y_score=y_p)
    AUPR_norm = AUPR/np.mean(y_t)


    return AUC, AUPR, AUPR_norm


AUROC_total = []
AUPRC_total = []
for rounds in [1,2,3,4,5]:

    test_file = './demo_data/GRN_inference/input/mesc2/Test_set' + str(rounds) + '.csv'
    file_path = "./result/mesc2/GRN_inference.csv"  # 替换为你的文件路径
    #file_path = "./data/mHSC-L/mL_network.csv"  # 替换为你的文件路径
    test_data = pd.read_csv(test_file, index_col=0).values
    pre_data = pd.read_csv(file_path,header=None).values

    print(test_data)
    print(pre_data)

    #print(pre_data.head())
    score = []
    f_test_data = []

    ## 将pre_data转化成字典，实现快速匹配
    # 使用列表推导式和字典推导式将列表转换为字典
    result = {tuple(item[:2]): item[2] for item in pre_data}

    # 获取键值对 (2, 3) 对应的值
    #value = result[(2, 3)]
    count = 0
    for i in test_data:
        key = (i[0],i[1])
        if key in result:
            value = result[key]
            # count = count + 1
            # print(count)
            score.append(value)
            f_test_data.append(i[2])

    # for i in test_data:
    #     for j in pre_data:
    #         if i[0] == j[0] and i[1] == j[1]:
    #             score.append(j[2])

    # print(i[0],i[1],j[0],j[1],j[2])
    print("score:{}".format(score))
    print(len(f_test_data))
    print(len(score))

    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    score = (torch.from_numpy(np.array(score))).to(device)
    f_test_data = (torch.from_numpy(np.array(f_test_data))).to(device)

    print(f_test_data)
    print(score)

    AUC, AUPR, AUPR_norm = Evaluation(y_pred=score, y_true=f_test_data)
    print("AUC:{}".format(AUC))
    print("AUPR:{}".format(AUPR))

    AUROC_total.append(round(AUC,3))
    AUPRC_total.append(round(AUPR,3))

print("AUROC_total:{}".format(AUROC_total))
print("AUPRC_total:{}".format(AUPRC_total))
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

    test_file = './input/mHSC-L/Test_set' + str(rounds) + '.csv'
    file_path = "./output/mHSC-L/predicted_GRN.csv"  # 替换为你的文件路径
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

    AUROC_total.append(round(AUC, 3))
    AUPRC_total.append(round(AUPR, 3))

print("AUROC_total:{}".format(AUROC_total))
print("AUPRC_total:{}".format(AUPRC_total))
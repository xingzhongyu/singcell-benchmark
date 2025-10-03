import os
import pandas as pd

from arboreto.algo import grnboost2, genie3
from arboreto.utils import load_tf_names
from distributed import Client, LocalCluster


import random





if __name__ == '__main__':

    net1_ex_path = './B1.csv'
    net1_tf_path = './TF.csv'


    ex_matrix = pd.read_csv(net1_ex_path,index_col=0)
    #tf_names = load_tf_names(net1_tf_path)
    tf = pd.read_csv(net1_tf_path)
    tf_names = list(tf['TF'].values)
    #tf_names = [str(i) for i in tf_names]

    ex_matrix = ex_matrix.T
    #ex_matrix.columns = [str(i) for i in range(692)] ##(1204,1071),(1132,889),(692,847)
    print(ex_matrix.head())
    print(tf_names)



    #network = genie3(expression_data=ex_matrix,tf_names=tf_names)

    # instantiate a custom Dask distributed Client
    client = Client(LocalCluster())

    # compute the GRN
    network = grnboost2(expression_data=ex_matrix,
                        tf_names=tf_names,
                        client_or_address=client)

    # print(network.head())
    # max_value = network['importance'].max()
    # network['importance'] = network['importance'] / max_value

    print("调控得分：{}".format(network.head(50)))

    network.to_csv('./B1_network5.csv',header=False, index=False)



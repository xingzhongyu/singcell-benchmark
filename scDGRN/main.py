import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from torch.optim import Adam
from torch.utils.data import DataLoader
import os
import io
import zipfile
import warnings
from typing import List, Dict

# --- FastAPI and related imports ---
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from contextlib import asynccontextmanager

# --- Model and Utility imports ---
try:
    from gTrans_dgrn import GTransformer
    from utils import scRNADataset, adj2saprse_tensor
except ImportError:
    raise RuntimeError(
        "Could not import GTransformer or utils. "
        "Please ensure gTrans_dgrn.py and utils.py are in the same directory as this script."
    )

warnings.filterwarnings("ignore")

# --- Configuration Section ---
class AppConfig:
    D_TYPE = 'hesc2'
    # Paths to static data files required for training structure and final prediction
    TF_FILE = f'./processed_data/{D_TYPE}/TF.csv'
    GENE_FILE = f'./processed_data/{D_TYPE}/gene_index1000.csv'
    TRAIN_SET_FILE = f'./processed_data/{D_TYPE}/Train_set1.csv'
    
    # Model hyperparameters
    MODEL_INPUT_DIM = 85
    HIDDEN_DIM = [128, 64, 32]
    OUTPUT_DIM = 16
    NUM_HEAD = [3, 3]
    ALPHA = 0.2
    TYPE = 'dot'
    REDUCTION = 'concate'
    
    # Training hyperparameters
    LEARNING_RATE = 3e-3
    EPOCHS = 5  # Keep this low for a responsive API, or handle as a long-running task
    BATCH_SIZE = 512
    
    # Inference parameters
    TIME_POINTS = 6
    TOP_PERCENT_THRESHOLD = 0.2

# Use CUDA if available, otherwise CPU
DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# --- Global Cache and Lifespan Management ---
cached_data = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup.
    Loads STATIC data assets needed for every training run into the cache.
    This avoids reading files from disk on every API call.
    """
    print("Application starting up...")
    print(f"Using device: {DEVICE}")

    # --- 1. Load static training structure and TF/gene lists ---
    print("Caching static data assets...")
    train_df = pd.read_csv(AppConfig.TRAIN_SET_FILE, index_col=0)
    cached_data["train_data"] = torch.from_numpy(train_df.values).to(DEVICE)
    
    tf_df = pd.read_csv(AppConfig.TF_FILE)
    tf_indices = torch.from_numpy(tf_df['index'].values.astype(np.int64))

    # --- 2. Prepare and cache the Adjacency Matrix ---
    num_genes_in_adj = max(train_df['TF'].max(), train_df['Target'].max()) + 1
    train_loader_util = scRNADataset(train_df.values, num_genes_in_adj, flag=False)
    adj_matrix = train_loader_util.Adj_Generate(tf_indices, loop=False)
    cached_data["adj"] = adj2saprse_tensor(adj_matrix).to(DEVICE)

    # --- 3. Prepare and cache the full TF-Target pair set for final inference ---
    gene_df = pd.read_csv(AppConfig.GENE_FILE)
    tf_all = tf_df['index'].tolist()
    target_all = gene_df['gene_index'].tolist()
    exp_pairs = [[tf, target] for tf in tf_all for target in target_all]
    cached_data["exp_data_tensor"] = torch.tensor(exp_pairs, device=DEVICE)
    cached_data["exp_data_df"] = pd.DataFrame(exp_pairs, columns=['TF', 'Target'])
    
    print("Static data assets loaded and cached.")
    yield
    cached_data.clear()
    torch.cuda.empty_cache()
    print("Application shut down.")

# --- FastAPI Application Instance ---
app = FastAPI(
    title="Dynamic GRN Training and Inference API",
    description=(
        "Upload time-series gene expression data to train a model from scratch "
        "and infer a dynamic gene regulatory network."
    ),
    lifespan=lifespan
)

# --- Core Training and Inference Logic ---
def perform_grn_inference_with_training(expression_dfs: List[pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    This function contains the full pipeline:
    1. Initializes a new GTransformer model.
    2. Trains the model using the user-provided expression data.
    3. Uses the trained model to infer the GRN for all time points.
    """
    try:
        # --- 1. Preprocess user's expression data ---
        data_features = [
            torch.from_numpy(df.apply(lambda x: np.log2(x + 0.1)).to_numpy()).float().to(DEVICE)
            for df in expression_dfs
        ]

        # --- 2. Retrieve cached static data ---
        adj = cached_data["adj"]
        train_data = cached_data["train_data"]
        exp_data_tensor = cached_data["exp_data_tensor"]
        exp_data_df = cached_data["exp_data_df"]

        # --- 3. Initialize a NEW model and optimizer for this request ---
        print("Initializing new model for this request...")
        model = GTransformer(
            input_dim=AppConfig.MODEL_INPUT_DIM,
            hidden1_dim=AppConfig.HIDDEN_DIM[0],
            hidden2_dim=AppConfig.HIDDEN_DIM[1],
            hidden3_dim=AppConfig.HIDDEN_DIM[2],
            output_dim=AppConfig.OUTPUT_DIM,
            num_head1=AppConfig.NUM_HEAD[0],
            num_head2=AppConfig.NUM_HEAD[1],
            alpha=AppConfig.ALPHA, device=DEVICE, type=AppConfig.TYPE, reduction=AppConfig.REDUCTION
        ).to(DEVICE)
        
        optimizer = Adam(model.parameters(), lr=AppConfig.LEARNING_RATE)

        # --- 4. Training Loop ---
        print(f"Starting training for {AppConfig.EPOCHS} epochs...")
        # Create a DataSet from the cached training pairs for the DataLoader
        train_dataset = torch.utils.data.TensorDataset(train_data[:, :-1], train_data[:, -1].float())
        
        for epoch in range(AppConfig.EPOCHS):
            model.train()
            running_loss = 0.0
            
            # The DataLoader uses the static training pairs (TF, Target, label)
            for train_x, train_y in DataLoader(train_dataset, batch_size=AppConfig.BATCH_SIZE, shuffle=True):
                optimizer.zero_grad()
                
                train_y = train_y.to(DEVICE).view(-1, 1).float()
                
                # The model uses the USER'S expression data for features
                pred, _, _ = model(data_features, adj, train_x, recons_tp=AppConfig.TIME_POINTS)
                pred = torch.sigmoid(pred)
                
                loss = F.binary_cross_entropy(pred, train_y)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()

            print(f"Epoch: {epoch + 1}, Train Loss: {running_loss / len(train_dataset):.6f}")
        
        print("Training finished.")

        # --- 5. Inference using the newly trained model ---
        print("Performing final inference on all TF-Target pairs...")
        model.eval()
        results = {}
        with torch.no_grad():
            for i in range(AppConfig.TIME_POINTS):
                recons_tp = i + 1
                
                score, _, _ = model(data_features, adj, exp_data_tensor, recons_tp)
                score = torch.sigmoid(score).cpu().flatten().numpy()

                result_df = exp_data_df.copy()
                result_df['score'] = score
                
                df_sorted = result_df.sort_values(by='score', ascending=False)
                num_rows = int(len(df_sorted) * AppConfig.TOP_PERCENT_THRESHOLD)
                df_top = df_sorted.head(num_rows)
                
                results[f"t{recons_tp}"] = df_top
        
        return results

    except Exception as e:
        print(f"Error during GRN training/inference: {e}")
        import traceback
        traceback.print_exc()
        raise

# --- API Endpoint ---
@app.post("/infer-grn-with-training/")
async def train_and_infer_network(
    expression_zip: UploadFile = File(..., description="A ZIP archive containing 6 chronologically named CSV files of gene expression data.")
):
    """
    Accepts a ZIP file of expression data, trains a new model, infers the GRN,
    and returns the predicted regulatory networks for each time point.
    **Warning:** This is a computationally expensive operation and may take a long time.
    """
    if not expression_zip.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP archive.")

    try:
        contents = await expression_zip.read()
        zip_buffer = io.BytesIO(contents)
        expression_dfs = []
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = sorted(zf.namelist())
            if len(file_list) != AppConfig.TIME_POINTS:
                raise HTTPException(status_code=400, detail=f"Expected {AppConfig.TIME_POINTS} files, but found {len(file_list)}.")
            for filename in file_list:
                with zf.open(filename) as f:
                    expression_dfs.append(pd.read_csv(io.BytesIO(f.read()), index_col=0))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse ZIP archive or CSV files: {e}")

    try:
        print("Starting GRN training and inference in a background thread...")
        result_dict = await run_in_threadpool(perform_grn_inference_with_training, expression_dfs)
        print("GRN processing completed successfully.")
        json_output = {key: df.to_dict(orient='records') for key, df in result_dict.items()}
        return json_output
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred during processing: {e}")

@app.get("/")
async def root():
    return {"message": "Welcome to the Dynamic GRN Training and Inference API.", "docs_url": "/docs"}
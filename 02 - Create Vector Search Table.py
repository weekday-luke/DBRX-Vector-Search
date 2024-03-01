# Databricks notebook source
!pip install torch transformers datasets

# COMMAND ----------

#load images
from datasets import load_dataset

imagenette = load_dataset(
  'frgfm/imagenette',
  'full_size',
  split='train',
  ignore_verifications=False
)

imagenette[0]["image"]

# COMMAND ----------

#load model
from transformers import CLIPTokenizerFast, CLIPProcessor, CLIPModel
import torch

device = "cuda" if torch.cuda.is_available() else \
          ("mps" if torch.backends.mps.is_available() else "cpu")
model_id = "openai/clip-vit-base-patch32"


model = CLIPModel.from_pretrained(model_id).to(device)
tokenizer = CLIPTokenizerFast.from_pretrained(model_id)
processor = CLIPProcessor.from_pretrained(model_id)

# COMMAND ----------

prompt = "a dog in the snow"

#tokenize the prompt

inputs = tokenizer(prompt, return_tensors="pt")
inputs

# COMMAND ----------

text_emb = model.get_text_features(**inputs)
text_emb.shape

# COMMAND ----------

#resizing the image with proceessor
#expected shape is torch.Size([1, 3, 224, 224])
image = processor(text=None,
                  images = imagenette[0]['image'],
                  return_tensors="pt")['pixel_values'].to(device)
image.shape

# COMMAND ----------

import matplotlib.pyplot as plt

#resize the image and show it
#the pixels have been modified which is why the image looks distorted
plt.imshow(image.squeeze(0).T)

# COMMAND ----------

#after this line you will have a 512 dimension embedding vector
image_emb = model.get_image_features(image)
image_emb.shape

# COMMAND ----------

#get a subset of 100 images for this experiment
import numpy as np

np.random.seed(0)
sample_idx = np.random.randint(0, len(imagenette)+1,100).tolist()
images = [imagenette[i]['image'] for i in sample_idx]
len(images)

# COMMAND ----------

# DBTITLE 1,Image Batch Embedding Processor
from tqdm.auto import tqdm

batch_size = 16
image_arr = None

for i in tqdm(range(0, len(images), batch_size)):
  #select batch of images
  batch = images[i:i+batch_size]
  #process and resize images
  batch = processor(text=None,
                  images = batch,
                  return_tensors="pt",
                  padding=True,
                  is_train=False)['pixel_values'].to(device)
  
  #get image embeddings
  batch_emb = model.get_image_features(pixel_values=batch)
  #convert to numpy array
  batch_emb = batch_emb.squeeze(0)
  batch_emb = batch_emb.cpu().detach().numpy()
  #add to larger array of all image embeddings
  if image_arr is None:
    image_arr = batch_emb
  else:
    image_arr = np.concatenate((image_arr, batch_emb), axis=0)

# COMMAND ----------

from pyspark.sql.functions import col
from pyspark.sql.types import ArrayType, FloatType

# Assuming `spark` is your SparkSession and `df` is your existing DataFrame

# Step 1: Convert the numpy array to a list of lists
image_list = image_arr.tolist()

# Step 2: Create a new DataFrame from the list of lists
rdd = spark.sparkContext.parallelize(image_list)
schema = ArrayType(FloatType())
image_df = rdd.map(lambda x: (x,)).toDF(schema=["image_embeddings"])

# COMMAND ----------

# Convert DataFrame to RDD
df_rdd = image_df.rdd

# Zip with index (which returns a new RDD)
rdd_with_index = df_rdd.zipWithIndex()

# Convert the resulting RDD into a DataFrame
# The result is a tuple where the first element is the original row and the second element is the index
df_with_index = rdd_with_index.map(lambda row: (row[1],) + tuple(row[0])).toDF(["index"] + image_df.columns)

# Now df_with_index is the same as df but with an additional "index" column

# COMMAND ----------

df_with_index.display()

# COMMAND ----------

images = spark.table("field_demos.luke_sandbox.images")

# COMMAND ----------

# Assuming the 'images' DataFrame has already been read into the 'images' variable
images_rdd = images.rdd

# Zip with index (which returns an RDD of pairs)
images_rdd_with_index = images_rdd.zipWithIndex()

# Map to a DataFrame by including the index
# The lambda function maps the original row (row[0]) and the index (row[1]) to a new row
images_with_index = images_rdd_with_index.map(
    lambda row: (row[1],) + tuple(row[0])
).toDF(["index"] + images.columns)

# Show the new DataFrame with the index
images_with_index.display()

# COMMAND ----------



import os

root_dirs = [r"..\dataset1", r"..\dataset2", r"..\dataset3"]
output_file = "dataset_info.txt"

with open(output_file, "w") as f:
    for root in root_dirs:
        if os.path.exists(root):
            dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
            f.write(f"Dataset: {root}\n")
            f.write(f"Count: {len(dirs)}\n")
            f.write(f"Classes: {dirs}\n\n")
        else:
            f.write(f"Dataset {root} not found.\n")

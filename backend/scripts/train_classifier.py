"""Train the local SetFit + MiniLM WhatsApp classifier."""
import argparse
import json
import os
import sys

LABELS = [
    "noise",
    "assignment_deadline",
    "exam",
    "lecture_update",
    "event",
    "fee_notice",
    "general_announcement",
]


def _repo_path(*parts: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), *parts))


def train(data_path: str, model_save_path: str):
    data_path = os.path.abspath(data_path)
    model_save_path = os.path.abspath(model_save_path)

    if not os.path.exists(data_path):
        print(f"Error: Training data not found at {data_path}. Run seed_training_data.py first.")
        sys.exit(1)

    print("Checking dependencies...")
    try:
        import torch
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except ImportError as e:
        print(f"\nMissing dependency: {e.name}")
        print("To train the classifier, please install the required packages:")
        print("  pip install setfit datasets torch")
        print("\nNote: The backend will fall back to anchor-based semantic classification")
        print("if SetFit is not installed or the model is not trained.")
        sys.exit(1)

    print(f"Loading training data from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    # Prepare datasets for SetFit
    # We want a multi-class classification task.
    # SetFit maps categories to integer IDs.
    categories = [label for label in LABELS if any(s["category"] == label for s in samples)]
    unknown = sorted({s["category"] for s in samples} - set(LABELS))
    if unknown:
        print(f"Error: unsupported categories in training data: {unknown}")
        sys.exit(1)
    missing = [label for label in LABELS if label not in categories]
    if missing:
        print(f"Warning: missing categories in training data: {missing}")
    cat_to_id = {cat: i for i, cat in enumerate(categories)}
    id_to_cat = {i: cat for i, cat in enumerate(categories)}

    print(f"Classes: {categories}")
    
    texts = [s["text"] for s in samples]
    labels = [cat_to_id[s["category"]] for s in samples]

    # Create HuggingFace Dataset
    dataset = Dataset.from_dict({
        "text": texts,
        "label": labels
    })

    print("Initializing SetFit model (sentence-transformers/all-MiniLM-L6-v2 base)...")
    # Load a pretrained SentenceTransformer and add a linear classification head
    model = SetFitModel.from_pretrained(
        "sentence-transformers/all-MiniLM-L6-v2",
        labels=categories
    )

    print("Configuring training arguments...")
    # Define training arguments. We use a small number of epochs/iterations for rapid training
    args = TrainingArguments(
        batch_size=16,
        num_epochs=1,  # Number of epochs on contrastive training
        num_iterations=20,  # Number of pairs to generate for contrastive training
        use_amp=False  # Set to True if GPU available with mixed precision
    )

    print("Starting training...")
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        column_mapping={"text": "text", "label": "label"}
    )
    
    trainer.train()

    print(f"Saving model to {model_save_path}...")
    os.makedirs(model_save_path, exist_ok=True)
    model.save_pretrained(model_save_path)

    # Save mapping metadata
    metadata = {
        "cat_to_id": cat_to_id,
        "id_to_cat": id_to_cat,
        "labels": categories
    }
    with open(os.path.join(model_save_path, "model_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\nSetFit model successfully trained and saved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default=_repo_path("app", "models", "training_data.json"),
        help="Path to JSON training data with text/category/urgency fields.",
    )
    parser.add_argument(
        "--output",
        default=_repo_path("app", "models", "setfit_classifier"),
        help="Directory where the trained SetFit model should be saved.",
    )
    args = parser.parse_args()
    train(args.data, args.output)

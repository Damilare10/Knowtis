"""
Export confirmed/corrected production feedback into SetFit training_data.json.

This script does not train the model. It builds a sanitized dataset that can be
reviewed, then passed to scripts/train_classifier.py.
"""
import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models import FeedbackType, TrainingFeedback
from app.services.training_feedback_service import TrainingFeedbackService


def export(output_path: str, min_items: int) -> int:
    output_path = os.path.abspath(output_path)
    db = SessionLocal()
    try:
        rows = db.query(TrainingFeedback).join(TrainingFeedback.prediction).all()
        samples = []
        seen = set()

        for feedback in rows:
            prediction = feedback.prediction
            if not prediction or not prediction.message_text:
                continue
            if feedback.feedback_type == FeedbackType.NOT_ACADEMIC:
                category = "noise"
            else:
                category = TrainingFeedbackService.category_for_feedback(
                    prediction,
                    feedback.corrected_category,
                )

            text = TrainingFeedbackService.sanitize_message(prediction.message_text)
            if not text:
                continue

            key = (text.lower(), category)
            if key in seen:
                continue
            seen.add(key)

            samples.append({
                "text": text,
                "category": category,
                "urgency": "medium",
            })

        if len(samples) < min_items:
            print(f"Warning: only {len(samples)} samples exported; target is {min_items}.")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(samples, f, indent=2)

        print(f"Exported {len(samples)} sanitized training samples to {output_path}")
        return len(samples)
    finally:
        db.close()


if __name__ == "__main__":
    backend_root = os.path.dirname(os.path.dirname(__file__))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=os.path.join(backend_root, "app", "models", "training_data.json"),
    )
    parser.add_argument("--min-items", type=int, default=100)
    args = parser.parse_args()
    export(args.output, args.min_items)

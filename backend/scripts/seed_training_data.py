"""
Script to generate a rich training dataset of WhatsApp messages for student groups.
Generates 700+ examples across noise, assignment_deadline, exam, lecture_update,
event, fee_notice, and general_announcement categories, labeled with urgency.
"""
import json
import random
import os

# Define constants for generation
COURSE_CODES = ["CSC301", "CSC401", "ELE310", "MCE402", "PHY101", "GNS201", "CHM101", "CVE202", "MEE311", "STA202"]
LECTURERS = ["Dr. Taiwo", "Prof. Adebayo", "Dr. Okon", "Mrs. Ibrahim", "Dr. Eze", "Engr. Yusuf", "Dr. Balogun"]
VENUES = ["LT1", "LT2", "LLT", "BLT", "ELT", "Auditorium", "Room 405", "CSC Lab", "Engineering Lecture Theatre"]
DAYS = ["today", "tomorrow", "Friday", "next Monday", "Wednesday", "Thursday", "Saturday", "this evening"]
TIMES = ["8:00 AM", "10:00 AM", "12:00 PM", "2:00 PM", "4:00 PM", "9:00 AM", "12pm", "4pm"]
REASONS = ["rain", "health issues", "senate meeting", "unforeseen circumstances", "power outage", "clashing schedule"]
TOPICS = ["Artificial Intelligence", "Machine Learning", "Web Development", "Microcontrollers", "Data Science", "Career Development"]

CATEGORIES = [
    "noise", "assignment_deadline", "exam", "lecture_update", "event", "fee_notice", "general_announcement"
]

URGENCIES = ["low", "medium", "high", "critical"]

def generate_dataset():
    random.seed(42)  # For reproducibility
    dataset = []

    # 1. Generate Noise (needs to be about 30% of the dataset)
    noise_templates = [
        "Haha that is funny 😂",
        "Who has the PDF for {course}?",
        "Can someone explain question {num} to me?",
        "Good morning guys",
        "Happy weekend everyone!",
        "Thanks a lot",
        "Please send the link again",
        "Who is in school?",
        "Is anyone at the department?",
        "😂😂😂",
        "Please add my friend to this group: {phone}",
        "Guys, did we have class yesterday?",
        "Who took my notebook in {venue}?",
        "Please help me check if the lecturer is in his office",
        "I need a study partner for {course}",
        "LOL",
        "Ok",
        "Alright",
        "Yes o",
        "No class today? I'm already at the gate",
        "Who has extra pen?",
        "Please when is the deadline? (just asking, no info)",
        "Is the assignment hard?",
        "My portal is not opening, anyone else?",
        "Happy birthday {name}!",
        "I don't think there is any class",
    ]
    
    names = ["John", "Chidi", "Aminu", "Sarah", "Tunde", "Blessing", "Emeka", "Fatima"]
    for _ in range(250):
        t = random.choice(noise_templates)
        text = t.format(
            course=random.choice(COURSE_CODES),
            num=random.randint(1, 5),
            venue=random.choice(VENUES),
            phone=f"080{random.randint(10000000, 99999999)}",
            name=random.choice(names)
        )
        dataset.append({
            "text": text,
            "category": "noise",
            "urgency": "low"
        })

    # 2. Generate Assignment Deadlines
    assignment_templates = [
        "{course} assignment due {day} by {time}",
        "Kindly submit your {course} project on {day}.",
        "Deadline for {course} homework has been moved to {day} at {time}.",
        "Make sure you upload your {course} assignment before {time} {day}.",
        "We are to submit our lab reports for {course} to {lecturer} by {time} {day}.",
        "The {course} assignment portal closes {day}.",
        "Urgent: {course} assignment submission deadline is {day} {time}!",
        "Don't forget to submit the {course} assignment {day}."
    ]
    
    for _ in range(100):
        t = random.choice(assignment_templates)
        day = random.choice(DAYS)
        text = t.format(
            course=random.choice(COURSE_CODES),
            day=day,
            time=random.choice(TIMES),
            lecturer=random.choice(LECTURERS)
        )
        # Determine urgency
        urgency = "medium"
        if day in ["today", "tomorrow", "this evening"] or "urgent" in text.lower():
            urgency = "critical" if day == "today" else "high"
        
        dataset.append({
            "text": text,
            "category": "assignment_deadline",
            "urgency": urgency
        })

    # 3. Generate Exams/Tests
    exam_templates = [
        "CA test for {course} is scheduled for {day} at {time} in {venue}.",
        "Midterm exam for {course} holds {day} in {venue}.",
        "Timetable update: {course} exam is on {day} by {time}.",
        "Please be informed that the {course} quiz will hold {day} in {venue}.",
        "Prepare for {course} exam on {day}.",
        "Emergency: {course} test has been brought forward to {day} {time}!",
        "Final exam for {course} starts {day} {time}."
    ]
    for _ in range(100):
        t = random.choice(exam_templates)
        day = random.choice(DAYS)
        text = t.format(
            course=random.choice(COURSE_CODES),
            day=day,
            time=random.choice(TIMES),
            venue=random.choice(VENUES)
        )
        urgency = "high"
        if day in ["today", "tomorrow"] or "emergency" in text.lower():
            urgency = "critical"
        elif "next" in day.lower():
            urgency = "medium"
            
        dataset.append({
            "text": text,
            "category": "exam",
            "urgency": urgency
        })

    # 4. Generate Lecture Updates (cancellations/reschedules)
    lecture_templates = [
        "No class for {course} {day}. {lecturer} is not around.",
        "{course} lecture scheduled for {time} {day} has been postponed to {new_day} at {new_time}.",
        "Please note: {course} class is moved from {venue} to {new_venue} {day}.",
        "Class cancelled: {lecturer} will not hold {course} today due to {reason}.",
        "Emergency {course} class tomorrow morning at {time} in {venue}.",
        "{course} lecture has been rescheduled to {new_day} {new_time}.",
        "{lecturer} wants us to meet at {venue} by {time} {day} instead of normal venue."
    ]
    for _ in range(120):
        t = random.choice(lecture_templates)
        day = random.choice(DAYS)
        text = t.format(
            course=random.choice(COURSE_CODES),
            day=day,
            time=random.choice(TIMES),
            lecturer=random.choice(LECTURERS),
            venue=random.choice(VENUES),
            new_venue=random.choice([v for v in VENUES if v != random.choice(VENUES)]),
            new_day=random.choice(["Friday", "next Monday", "Wednesday"]),
            new_time=random.choice(TIMES),
            reason=random.choice(REASONS)
        )
        urgency = "high"
        if day in ["today", "tomorrow"] or "emergency" in text.lower() or "class cancelled" in text.lower():
            urgency = "critical"
            
        dataset.append({
            "text": text,
            "category": "lecture_update",
            "urgency": urgency
        })

    # 5. Generate Events
    event_templates = [
        "Guest lecture on {topic} holding {day} at {time} in {venue}.",
        "Workshop on {topic} for all {course} students this weekend.",
        "Join the tech seminar on {topic} {day} by {time} at {venue}.",
        "Departmental orientation program starts {day} at {time}.",
        "Hackathon briefing on {topic} is on {day} in the {venue}.",
        "Annual Student Meetup is scheduled for {day} {time}."
    ]
    for _ in range(60):
        t = random.choice(event_templates)
        text = t.format(
            topic=random.choice(TOPICS),
            day=random.choice(DAYS),
            time=random.choice(TIMES),
            venue=random.choice(VENUES),
            course=random.choice(COURSE_CODES)
        )
        dataset.append({
            "text": text,
            "category": "event",
            "urgency": "low"
        })

    # 6. Generate Fee Notices
    fee_templates = [
        "School fees payment portal closes on {day}. Ensure you pay up.",
        "Notice: Departmental dues of N5,000 should be paid before {day}.",
        "Deadline for hostel fee payment has been extended to {day}.",
        "Urgent: Pay your exam fees by {time} {day} to avoid being barred.",
        "Please pay your faculty association dues to the financial secretary.",
        "Important fee notice: Check portal for new registration payment details."
    ]
    for _ in range(50):
        t = random.choice(fee_templates)
        day = random.choice(DAYS)
        text = t.format(
            day=day,
            time=random.choice(TIMES)
        )
        urgency = "medium"
        if day in ["today", "tomorrow"] or "urgent" in text.lower() or "closes" in text.lower():
            urgency = "critical"
        elif "extended" in text.lower():
            urgency = "high"
            
        dataset.append({
            "text": text,
            "category": "fee_notice",
            "urgency": urgency
        })

    # 7. Generate General Announcements
    announcement_templates = [
        "Kindly note that we are wearing white and black on {day}.",
        "Check your student portal, {course} results have been uploaded.",
        "Please sign the attendance registry in the department office before {day}.",
        "Course registration forms must be submitted by Friday.",
        "All course reps are requested to meet {lecturer} at {time} today.",
        "Collect your student ID cards from the admin office starting tomorrow."
    ]
    for _ in range(60):
        t = random.choice(announcement_templates)
        day = random.choice(DAYS)
        text = t.format(
            day=day,
            course=random.choice(COURSE_CODES),
            lecturer=random.choice(LECTURERS),
            time=random.choice(TIMES)
        )
        urgency = "medium"
        if "today" in text.lower():
            urgency = "high"
        elif "form" in text.lower() or "submit" in text.lower():
            urgency = "high"
            
        dataset.append({
            "text": text,
            "category": "general_announcement",
            "urgency": urgency
        })

    # Shuffle dataset
    random.shuffle(dataset)
    
    print(f"Generated {len(dataset)} examples total.")
    counts = {}
    for item in dataset:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    print("Category breakdown:")
    for cat, cnt in counts.items():
        print(f"  {cat}: {cnt}")
        
    return dataset

if __name__ == "__main__":
    data = generate_dataset()
    backend_root = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(backend_root, "app", "models")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "training_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved dataset to {out_path}")

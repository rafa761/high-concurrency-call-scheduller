#!/usr/bin/env python3
"""Reproducible contact-data generator.

Produces a CSV matching the schema of data/sample-contacts.csv:
    phone,first_name,last_name,timezone,account_ref,amount_due

Uses only the Python standard library.
"""

import argparse
import csv
import random

FIRST_NAMES = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David",
    "Susan", "Christopher", "Jennifer", "Daniel", "Karen", "Mark", "Nancy",
    "Steven", "Betty", "Paul", "Sandra", "Joshua", "Ashley", "Kevin",
    "Michelle", "Brian", "Amanda", "Jason", "Emily", "Andrew", "Olivia",
    "Anthony", "Sophia", "Joseph", "Isabella", "Ryan", "Grace", "Nathan",
    "Chloe", "Samuel", "Hannah", "Benjamin", "Victoria", "Elijah", "Lucia",
    "Omar", "Priya", "Wei", "Aisha", "Diego", "Yuki", "Ahmed", "Fatima",
]

LAST_NAMES = [
    "Carter", "Gonzalez", "Chen", "Okafor", "Novak", "Andersson", "Whitfield",
    "Lindgren", "Reyes", "Mwangi", "Petrov", "Sandoval", "Delacroix", "Iqbal",
    "Nakamura", "Rossi", "Kowalski", "Ferreira", "Adeyemi", "Thornton",
    "Sorensen", "Kahale", "Costa", "Beauchamp", "Mbeki", "Johnson", "Williams",
    "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson",
    "Thomas", "Jackson", "White", "Harris", "Martin", "Garcia", "Martinez",
    "Robinson", "Clark", "Lewis", "Lee", "Walker", "Hall", "Young", "King",
    "Wright",
]

# Weighted toward populous zones.
TIMEZONES = [
    ("America/New_York", 30),
    ("America/Chicago", 22),
    ("America/Denver", 10),
    ("America/Phoenix", 5),
    ("America/Los_Angeles", 25),
    ("America/Anchorage", 3),
    ("Pacific/Honolulu", 5),
]


def build_phone_pool(count, rng):
    """Return `count` globally-unique +1XXXXXXXXXX numbers."""
    phones = set()
    while len(phones) < count:
        # First digit of area code and exchange must be 2-9 to look valid.
        area = rng.randint(2, 9) * 100 + rng.randint(0, 99)
        exchange = rng.randint(2, 9) * 100 + rng.randint(0, 99)
        subscriber = rng.randint(0, 9999)
        phones.add(f"+1{area:03d}{exchange:03d}{subscriber:04d}")
    return list(phones)


def generate(count, output, seed):
    rng = random.Random(seed)

    tz_values = [tz for tz, _ in TIMEZONES]
    tz_weights = [w for _, w in TIMEZONES]

    phones = build_phone_pool(count, rng)
    rng.shuffle(phones)

    with open(output, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["phone", "first_name", "last_name", "timezone",
             "account_ref", "amount_due"]
        )
        for i in range(count):
            phone = phones[i]
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            timezone = rng.choices(tz_values, weights=tz_weights, k=1)[0]
            account_ref = f"ACC-2{(i + 1):05d}"
            amount_due = f"{rng.uniform(10.0, 5000.0):.2f}"
            writer.writerow(
                [phone, first, last, timezone, account_ref, amount_due]
            )

    print(f"Wrote {count} contacts to {output}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a reproducible contacts CSV."
    )
    parser.add_argument("--count", type=int, default=10000,
                        help="Number of rows to generate (default: 10000).")
    parser.add_argument("--output", default="data/contacts-10k.csv",
                        help="Output CSV path (default: data/contacts-10k.csv).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42).")
    args = parser.parse_args()

    generate(args.count, args.output, args.seed)


if __name__ == "__main__":
    main()

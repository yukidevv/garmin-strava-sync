from garminconnect import Garmin
from dotenv import load_dotenv
import os
import json

def main():
  load_dotenv()
  client = Garmin(
    os.getenv("GARMIN_EMAIL"),
    os.getenv("GARMIN_PASSWORD")
  )

  client.login(".garminconnect")

  sleep = client.get_sleep_data("2026-05-30")
  print(json.dumps(sleep["dailySleepDTO"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
  main()

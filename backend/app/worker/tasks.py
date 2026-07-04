import time
import random
import logging
from app.worker.registry import registry

logger = logging.getLogger("app.worker.tasks")

@registry.task("send_email")
def send_email(email: str, subject: str, body: str) -> dict:
    logger.info(f"Simulated email send - To: {email} | Subject: {subject} | Body: {body}")
    print(f"Sending email to {email} with subject '{subject}'...")
    time.sleep(0.5)
    print("Email sent successfully!")
    return {"status": "sent", "recipient": email, "timestamp": time.time()}

@registry.task("process_video")
def process_video(video_id: str, format: str = "mp4", resolution: str = "1080p") -> dict:
    print(f"Starting video transcoding for video_id={video_id} to resolution={resolution} and format={format}...")
    # Simulate transcoding progress
    for i in range(1, 4):
        time.sleep(1.0)
        print(f"Transcoding video {video_id}: {i * 33}% complete...")
    print("Video processing finished.")
    return {"status": "transcoded", "video_id": video_id, "resolution": resolution, "duration_sec": 3.0}

@registry.task("heavy_compute")
def heavy_compute(iterations: int = 100000) -> dict:
    print(f"Running compute-heavy algorithm with {iterations} iterations...")
    start_time = time.time()
    # Simple CPU-bound calculation
    result = 0.0
    for i in range(iterations):
        result += math_calc(i)
    elapsed = time.time() - start_time
    print(f"Computation complete in {elapsed:.3f} seconds.")
    return {"status": "computed", "result": result, "elapsed_seconds": elapsed}

def math_calc(x: int) -> float:
    return (x ** 2) * 0.0001

@registry.task("random_fail")
def random_fail(fail_rate: float = 0.5) -> dict:
    print(f"Executing random fail task (fail_rate = {fail_rate})...")
    time.sleep(0.5)
    r = random.random()
    if r < fail_rate:
        print("Task hit the random failure condition!")
        raise RuntimeError(f"Random failure occurred (rolled {r:.4f} < {fail_rate})")
    print("Task succeeded by chance!")
    return {"status": "succeeded", "rolled": r}

@registry.task("always_fail")
def always_fail(reason: str = "Specified failure") -> dict:
    print(f"Executing always fail task. Reason: {reason}...")
    time.sleep(0.2)
    raise ValueError(f"Task failed permanently: {reason}")

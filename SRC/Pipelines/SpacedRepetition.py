from datetime import date, timedelta

from Models.Session import MasteryScore


def state_to_quality(state: str) -> int:
    return {"correct": 5, "partial": 3, "wrong": 1, "stuck": 0}.get(state, 0)


class SM2:
    def update(self, score: MasteryScore, quality: int) -> MasteryScore:
        if quality < 3:
            score.repetitions = 0
            score.interval_days = 1
        else:
            score.easiness_factor = max(
                1.3,
                score.easiness_factor + 0.1 - (5 - quality) * 0.08,
            )
            if score.repetitions == 0:
                score.interval_days = 1
            elif score.repetitions == 1:
                score.interval_days = 6
            else:
                score.interval_days = max(
                    1, int(round(score.interval_days * score.easiness_factor))
                )
            score.repetitions += 1
        score.next_review_date = date.today() + timedelta(days=score.interval_days)
        return score

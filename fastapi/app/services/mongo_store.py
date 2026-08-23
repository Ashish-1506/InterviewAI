from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


@dataclass
class MongoStore:
    settings: Any


    def __post_init__(self) -> None:
        self._client = AsyncIOMotorClient(self.settings.mongo_uri)
        self._db = self._client[self.settings.mongo_db]
        self._sessions = self._db["interviewsessions"]

    async def get_interview_session(self, session_id: str) -> Optional[dict[str, Any]]:
        try:
            oid = ObjectId(session_id)
        except Exception:
            return None

        doc = await self._sessions.find_one({"_id": oid})
        if not doc:
            return None

        # Normalize for frontend/LLM logic.
        doc["id"] = str(doc.get("_id"))
        doc.pop("_id", None)
        return doc

    async def append_conversation_turn(
        self,
        session_id: str,
        turn_doc: dict[str, Any],
    ) -> None:
        oid = ObjectId(session_id)

        await self._sessions.update_one(
            {"_id": oid},
            {
                "$push": {"conversationTurns": turn_doc},
            },
        )

    async def update_last_conversation_turn(
        self,
        session_id: str,
        overlay: dict[str, Any],
    ) -> None:
        """Best-effort overlay for the most recent conversation turn."""
        oid = ObjectId(session_id)

        doc = await self._sessions.find_one(
            {"_id": oid},
            {"conversationTurns": 1},
        )
        if not doc:
            return

        turns = doc.get("conversationTurns") or []
        if not turns:
            return

        last_index = len(turns) - 1
        await self._sessions.update_one(
            {"_id": oid},
            {
                "$set": {f"conversationTurns.{last_index}.{k}": v for k, v in overlay.items()},
            },
        )

    async def update_conversation_turn(
        self,
        session_id: str,
        turn_index: int,
        overlay: dict[str, Any],
    ) -> None:
        """Overlay one known turn without accidentally modifying the next prompt."""
        oid = ObjectId(session_id)
        if turn_index < 0:
            return
        await self._sessions.update_one(
            {"_id": oid, f"conversationTurns.{turn_index}": {"$exists": True}},
            {"$set": {f"conversationTurns.{turn_index}.{k}": v for k, v in overlay.items()}},
        )

    async def append_emotion_sample(
        self,
        session_id: str,
        turn_index: Optional[int],
        scores: dict[str, float],
        timestamp_ms: Optional[int] = None,
    ) -> None:
        """Persist aggregated emotion only.

        Storage model:
        session document contains `emotionAnalysis.aggregatedByTurn` as an array.

        We store per-turn running aggregates as sums + counts, then derive averages.
        To keep this simple (and avoid Mongo $inc on nested array objects with unknown index),
        we upsert by searching the existing document in Python and updating it.
        """

        oid = ObjectId(session_id)

        session_doc = await self._sessions.find_one({"_id": oid})
        if not session_doc:
            return

        emotion_analysis = session_doc.get("emotionAnalysis") or {}
        aggregated_by_turn = emotion_analysis.get("aggregatedByTurn") or []

        # If turn_index is missing, attach to latest turn when available.
        # Best-effort: if no turns exist, fall back to 0.
        if turn_index is None:
            turns = session_doc.get("conversationTurns") or []
            turn_index = len(turns) - 1 if len(turns) > 0 else 0

        # Find existing turn bucket.
        bucket = None
        for b in aggregated_by_turn:
            if b.get("turn_index") == turn_index:
                bucket = b
                break

        if bucket is None:
            bucket = {
                "turn_index": int(turn_index),
                "sample_count": 0,
                "sum_scores": {k: 0.0 for k in scores.keys()},
            }
            aggregated_by_turn.append(bucket)

        bucket["sample_count"] = int(bucket.get("sample_count") or 0) + 1
        sum_scores = bucket.get("sum_scores") or {k: 0.0 for k in scores.keys()}
        for k, v in scores.items():
            sum_scores[k] = float(sum_scores.get(k, 0.0)) + float(v)
        bucket["sum_scores"] = sum_scores
        bucket["last_timestamp_ms"] = timestamp_ms

        # Recompute averages + basic trends (soft).
        # Trend: compare first half vs second half by storing running sample snapshots.
        # For simplicity, approximate by using count-weighted recentness is hard without timestamps,
        # so we emit trend as per-category delta between current average and global average.
        # (Still a trend/observation; not a diagnosis.)

        # Compute global averages across all buckets.
        total_samples = 0
        total_sum = {k: 0.0 for k in scores.keys()}
        for b in aggregated_by_turn:
            c = int(b.get("sample_count") or 0)
            total_samples += c
            ss = b.get("sum_scores") or {}
            for k in total_sum.keys():
                total_sum[k] = float(total_sum.get(k, 0.0)) + float(ss.get(k, 0.0))

        overall_avg = None
        if total_samples > 0:
            overall_avg = {k: float(total_sum[k] / total_samples) for k in total_sum.keys()}

        # Update each bucket's averages.
        for b in aggregated_by_turn:
            c = int(b.get("sample_count") or 0)
            ss = b.get("sum_scores") or {}
            averages = {k: float(ss.get(k, 0.0) / c) if c > 0 else 0.0 for k in total_sum.keys()}
            b["averages"] = averages

            trend = {}
            if overall_avg:
                for k, v in averages.items():
                    trend[k + "Delta"] = float(v - overall_avg.get(k, 0.0))
            b["trend"] = trend

        # Session summary (chart-ready series built at read time).
        emotion_analysis["enabled"] = True
        emotion_analysis["aggregatedByTurn"] = aggregated_by_turn

        await self._sessions.update_one(
            {"_id": oid},
            {
                "$set": {
                    "emotionAnalysis": emotion_analysis,
                }
            },
        )

    async def get_emotion_report(self, session_id: str) -> Optional[dict[str, Any]]:
        try:
            oid = ObjectId(session_id)
        except Exception:
            return None

        doc = await self._sessions.find_one({"_id": oid})
        if not doc:
            return None

        emotion_analysis = doc.get("emotionAnalysis") or {}
        aggregated_by_turn_raw = emotion_analysis.get("aggregatedByTurn") or []

        # Sort buckets by turn_index
        aggregated_by_turn_raw = sorted(aggregated_by_turn_raw, key=lambda x: x.get("turn_index", 0))

        # Build output.
        # Determine overall averages.
        total_samples = 0
        categories = ["confident", "nervous", "neutral", "engaged", "confused"]
        total_sum = {k: 0.0 for k in categories}
        for b in aggregated_by_turn_raw:
            c = int(b.get("sample_count") or 0)
            total_samples += c
            averages = b.get("averages") or {}
            for k in categories:
                total_sum[k] += float(averages.get(k, 0.0)) * c

        overall_averages = {k: float(total_sum[k] / total_samples) if total_samples > 0 else 0.0 for k in categories}

        dominant = sorted(categories, key=lambda k: overall_averages.get(k, 0.0), reverse=True)[:2]

        # Notable shifts: pick top 2 turns by absolute delta from overall avg for each category.
        notable_shifts: list[str] = []
        for cat in ["nervous", "engaged", "confused", "confident"]:
            best = None
            for b in aggregated_by_turn_raw:
                avg = (b.get("averages") or {}).get(cat, 0.0)
                delta = float(avg - overall_averages.get(cat, 0.0))
                if best is None or abs(delta) > abs(best[0]):
                    best = (delta, b)
            if best and abs(best[0]) > 0.05:
                b = best[1]
                ti = b.get("turn_index")
                avg = (b.get("averages") or {}).get(cat, 0.0)
                overall = overall_averages.get(cat, 0.0)
                direction = "increased" if avg > overall else "decreased"
                # Keep phrasing trend-only.
                notable_shifts.append(
                    f"{cat} {direction} around turn {ti} (avg {avg:.2f} vs overall {overall:.2f})."
                )

        aggregated_by_turn = []
        chart_series = {k: [] for k in categories}
        for b in aggregated_by_turn_raw:
            averages = b.get("averages") or {}
            trend = b.get("trend") or {}
            c = int(b.get("sample_count") or 0)
            ti = int(b.get("turn_index") or 0)

            aggregated_by_turn.append(
                {
                    "turn_index": ti,
                    "sample_count": c,
                    "averages": {k: float(averages.get(k, 0.0)) for k in categories},
                    "trend": trend,
                }
            )

            for k in categories:
                chart_series[k].append(float(averages.get(k, 0.0)))

        return {
            "session_id": str(doc.get("_id")),
            "aggregated_by_turn": aggregated_by_turn,
            "session_summary": {
                "overall_averages": {k: float(overall_averages.get(k, 0.0)) for k in categories},
                "dominant": dominant,
                "notable_shifts": notable_shifts,
            },
            "chart_series": chart_series,
        }





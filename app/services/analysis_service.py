"""分析用例服务。"""

from uuid import UUID

from engines.tasks.analysis_tasks import AnalysisTaskResult, run_analysis_task


class AnalysisService:
    """提交分析任务并保持幂等边界。"""

    def submit(self, document_version_id: UUID, idempotency_key: str) -> AnalysisTaskResult:
        """提交分析任务；Celery 未配置时显式失败。"""
        return run_analysis_task(document_version_id, idempotency_key)

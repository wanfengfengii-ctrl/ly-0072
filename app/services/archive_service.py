from typing import List, Dict, Any, Optional

from app.db.database import ReportArchiveRepository


class ArchiveService:
    @staticmethod
    def get_archives(report_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return ReportArchiveRepository.get_all(report_type=report_type)

    @staticmethod
    def create_archive(**kwargs) -> int:
        return ReportArchiveRepository.create(**kwargs)

    @staticmethod
    def delete_archive(archive_id: int) -> bool:
        return ReportArchiveRepository.delete(archive_id)

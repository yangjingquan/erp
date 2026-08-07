from pathlib import Path
import subprocess

from app.core.exceptions import AppError


def build_backup_command(target: Path) -> list[str]:
    target = Path(target).expanduser().resolve()
    if target.name in {"", ".", ".."} or target.suffix.lower() != ".sql":
        raise AppError("备份文件必须是 .sql 文件", code=400)
    return [
        "docker",
        "exec",
        "shop-mysql",
        "mysqldump",
        "--host=127.0.0.1",
        "--port=3306",
        "--user=root",
        "--password=changeme_root",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--databases",
        "erp",
        "--result-file",
        str(target),
    ]


def validate_restore_request(backup_path: Path, confirmation_token: str) -> bool:
    path = Path(backup_path).expanduser().resolve()
    if confirmation_token not in {"RESTORE_ERP", "RESTORE ERP"}:
        raise AppError("数据库恢复需要二次确认", code=400)
    if not path.is_file() or path.suffix.lower() != ".sql" or path.stat().st_size == 0:
        raise AppError("恢复文件不存在或不是有效 SQL 文件", code=400)
    return True


def run_backup(target: Path) -> Path:
    command = build_backup_command(target)
    target = Path(target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("wb") as output:
            subprocess.run(command[:-2], check=True, stdout=output, stderr=subprocess.PIPE, timeout=120)
    except FileNotFoundError as exc:
        raise AppError("未找到 Docker 或 shop-mysql 容器，请先启动 Docker 服务", code=500) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode(errors="replace").strip() if isinstance(exc.stderr, bytes) else str(exc.stderr or "").strip()
        raise AppError(f"数据库备份失败：{message}", code=500) from exc
    return target


def run_restore(backup_path: Path, confirmation_token: str) -> bool:
    validate_restore_request(backup_path, confirmation_token)
    command = [
        "docker",
        "exec",
        "-i",
        "shop-mysql",
        "mysql",
        "--host=127.0.0.1",
        "--port=3306",
        "--user=root",
        "--password=changeme_root",
        "erp",
    ]
    try:
        with Path(backup_path).open("rb") as stream:
            subprocess.run(command, stdin=stream, check=True, capture_output=True, timeout=120)
    except FileNotFoundError as exc:
        raise AppError("未找到 Docker 或 shop-mysql 容器，请先启动 Docker 服务", code=500) from exc
    except subprocess.CalledProcessError as exc:
        raise AppError("数据库恢复失败", code=500) from exc
    return True

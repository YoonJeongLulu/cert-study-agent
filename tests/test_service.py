import service


def test_log_directory_without_json_config_uses_database_directory(tmp_path):
    database_path = tmp_path / "data" / "study.sqlite3"
    assert service.log_directory(None, str(database_path)) == tmp_path / "data" / "logs"


def test_log_directory_with_json_config_uses_config_directory(tmp_path):
    config_path = tmp_path / "config" / "config.json"
    database_path = tmp_path / "data" / "study.sqlite3"
    assert service.log_directory(str(config_path), str(database_path)) == tmp_path / "config" / "logs"

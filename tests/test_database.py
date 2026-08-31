from app.database.connection import initialize_database

def test_database_is_created(tmp_path):
    path=tmp_path/"nested"/"history.db"; initialize_database(path)
    assert path.exists()

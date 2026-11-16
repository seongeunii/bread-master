"""Legacy-store fixture for regression tests that predate empty new stores."""
from app import db
from app.workspaces import migrate_legacy_workspaces
from app.quiz_groups import initialize_store_groups


def legacy_store(store_id):
    with db.connect() as conn:
        conn.execute('DELETE FROM workspace_metadata WHERE store_id=?', (store_id,))
        conn.execute('DELETE FROM store_categories WHERE store_id=?', (store_id,))
        conn.execute('DELETE FROM store_quiz_settings WHERE store_id=?', (store_id,))
        migrate_legacy_workspaces(conn)
        initialize_store_groups(conn,store_id)

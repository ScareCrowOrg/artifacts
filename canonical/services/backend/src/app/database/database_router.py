# import logging
# from typing import Optional
# logger = logging.getLogger(__name__)

# class DatabaseRouter:

#     def __init__(self, base_path=None, is_test_env=False):
#         from .connection import JSONDatabase
#         from app.tinydb_database import TinyDBDatabase

#         self.json_db = JSONDatabase(base_path=base_path, is_test_env=is_test_env)
#         self.tiny_db = TinyDBDatabase()  # TinyDBDatabase já tem padrão interno

#     def insert(self, collection, document, user_id: Optional[str] = None,
#         session_id: Optional[str] = None, is_canonical=True):
#         # Converte Pydantic model para dict se necessário
#         if hasattr(document, "model_dump"):
#             document = document.model_dump()
#         document = self._serialize_datetimes(document)
#         if is_canonical:
#             return self.json_db.insert(collection, document, user_id, session_id, is_canonical)
#         else:
#             return self.tiny_db.insert(collection, document, is_canonical)

#     def update(self, collection, doc_id, updates, user_id: Optional[str] = None, session_id: Optional[str] = None, is_canonical=True, key_field='id'):
#         # Converte Pydantic model para dict se necessário
#         logger.debug(f"DatabaseRouter.update called with collection={collection}, doc_id={doc_id}, is_canonical={is_canonical}, updates={updates}, user_id={user_id}, session_id={session_id}, key_field={key_field}")
#         if hasattr(updates, "model_dump"):
#             updates = updates.model_dump()
#         updates = self._serialize_datetimes(updates)
#         if is_canonical:
#             return self.json_db.update(collection, doc_id, updates, user_id, session_id, is_canonical=True)
#         else:
#             return self.tiny_db.update(collection, doc_id, updates, user_id, session_id, is_canonical=False, key_field=key_field)

#     @staticmethod
#     def _serialize_datetimes(obj):
#         """
#         Recursively convert datetime objects in dicts/lists to ISO strings for JSON serialization.
#         """
#         from datetime import datetime
#         if isinstance(obj, dict):
#             return {k: DatabaseRouter._serialize_datetimes(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [DatabaseRouter._serialize_datetimes(v) for v in obj]
#         elif isinstance(obj, datetime):
#             return obj.isoformat()
#         return obj

#     def find_one(self, collection, doc_id, *args, is_canonical=True, **kwargs):
#         if is_canonical:
#             return self.json_db.find_one(collection, doc_id, *args, is_canonical=True, **kwargs)
#         else:
#             return self.tiny_db.find_one(collection, doc_id, *args, is_canonical=False, **kwargs)

#     def find_many(self, collection, *args, is_canonical=True, model_class=None, **kwargs):
#         logger.debug(f"DatabaseRouter.find_many called with collection={collection}, is_canonical={is_canonical}, model_class={model_class}, args={args}, kwargs={kwargs}")
#         if is_canonical:
#             results = self.json_db.find_many(collection, *(args or []), is_canonical=True, **kwargs)
#         else:
#             results = self.tiny_db.find_many(collection, *(args or []), is_canonical=False, **kwargs)
#             # Converte cada resultado para model_class se necessário
#             if model_class:
#                 return [model_class(**self._deserialize_datetimes(r, model_class)) if not isinstance(r, model_class) else r for r in results]
#         return results

#     @staticmethod
#     def _deserialize_datetimes(obj, model_class=None):
#         """
#         Recursively convert ISO strings to datetime objects for fields expected as datetime in model_class.
#         """
#         from datetime import datetime
#         import re
#         if not model_class:
#             return obj
#         # Get expected datetime fields from model_class
#         datetime_fields = set()
#         if hasattr(model_class, '__annotations__'):
#             for k, v in model_class.__annotations__.items():
#                 if v.__name__ == 'datetime':
#                     datetime_fields.add(k)
#         def try_parse_datetime(val):
#             # ISO 8601 basic check
#             if isinstance(val, str) and re.match(r'^\d{4}-\d{2}-\d{2}T', val):
#                 try:
#                     return datetime.fromisoformat(val)
#                 except Exception:
#                     return val
#             return val
#         if isinstance(obj, dict):
#             return {k: try_parse_datetime(v) if k in datetime_fields else DatabaseRouter._deserialize_datetimes(v, None) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [DatabaseRouter._deserialize_datetimes(v, model_class) for v in obj]
#         return obj

#     def find_by_field(self, collection, field, value, *args, is_canonical=True, model_class=None, **kwargs):
#         if is_canonical:
#             result = self.json_db.find_by_field(collection, field, value, *(args or []), is_canonical=True, **kwargs)
#         else:
#             result = self.tiny_db.find_by_field(collection, field, value, *(args or []), is_canonical=False, **kwargs)
#             if model_class and result and not isinstance(result, model_class):
#                 return model_class(**self._deserialize_datetimes(result, model_class))
#         return result

#     def find_by_fields(self, collection, fields_dict, *args, is_canonical=True, model_class=None, **kwargs):
#         if is_canonical:
#             result = self.json_db.find_by_fields(collection, fields_dict, *(args or []), is_canonical=True, **kwargs)
#         else:
#             result = self.tiny_db.find_by_fields(collection, fields_dict, *(args or []), is_canonical=False, **kwargs)
#             if model_class and result and not isinstance(result, model_class):
#                 return model_class(**self._deserialize_datetimes(result, model_class))
#         return result

#     def query(self, collection, filter_dict, *args, is_canonical=True, **kwargs):
#         if is_canonical:
#             raise NotImplementedError("Query não suportado para dados canônicos (JSONDatabase). Use runtime (TinyDBDatabase).")
#         return self.tiny_db.query(collection, filter_dict, *args, is_canonical=False, **kwargs)


#     def get_config(self, config_key: str):
#         # Roteia para json_db, que implementa ConfigOperations
#         return self.json_db.get_config(config_key)

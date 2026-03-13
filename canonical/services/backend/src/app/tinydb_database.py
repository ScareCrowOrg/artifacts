# """
# Façade para TinyDB: interface NoSQL compatível para uso futuro com MongoDB.
# Compatível com interface do JSONDatabase para facilitar futura migração para MongoDB.
# """

# from tinydb import TinyDB, Query
# from typing import Optional, List, Dict, Any, Type, TypeVar
# import os
# from pydantic import BaseModel
# import logging

# logger = logging.getLogger(__name__)
# T = TypeVar('T', bound=BaseModel)

# class TinyDBDatabase:
#     def __init__(self, db_path=None):
#         if db_path is None:
#             db_path = os.path.join(os.path.dirname(__file__), 'scareverse_tinydb.json')
#         self.db = TinyDB(db_path)
#         raise RuntimeError("TinyDBDatabase is deprecated and should not be used in new code.")

#     def _check_soft_refs(self, collection, document):
#         import json
#         refs_path = os.path.join(os.path.dirname(__file__), 'refs_soft.json')
#         if not os.path.exists(refs_path):
#             return True  # No refs_soft defined
#         try:
#             with open(refs_path, 'r', encoding='utf-8') as f:
#                 refs_soft = json.load(f)
#         except Exception:
#             return True  # If can't load, skip check
#         for ref in refs_soft:
#             if ref.get('collection') == collection:
#                 prop = ref.get('property')
#                 if prop and prop in document:
#                     value = document[prop]
#                     # Check canonicalPath for JSON file with canonicalProperty == value
#                     canonical_path = ref.get('canonicalPath')
#                     canonical_prop = ref.get('canonicalProperty')
#                     if canonical_path and canonical_prop:
#                         # List all json files in canonicalPath
#                         import glob
#                         dir_path = canonical_path if os.path.isabs(canonical_path) else os.path.join(os.path.dirname(__file__), canonical_path)
#                         if not os.path.exists(dir_path):
#                             return False
#                         found = False
#                         for file in glob.glob(os.path.join(dir_path, '*.json')):
#                             try:
#                                 with open(file, 'r', encoding='utf-8') as f:
#                                     data = json.load(f)
#                                 if isinstance(data, dict) and data.get(canonical_prop) == value:
#                                     found = True
#                                     break
#                                 if isinstance(data, list):
#                                     for item in data:
#                                         if isinstance(item, dict) and item.get(canonical_prop) == value:
#                                             found = True
#                                             break
#                             except Exception:
#                                 continue
#                         if not found:
#                             return False
#         return True

#     def insert(self, collection, document, is_canonical=False):
#         table = self.db.table(collection)
#         return table.insert(document)

#     def find_one(self, collection, doc_id, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         table = self.db.table(collection)
#         result = table.get(Query()[key_field] == doc_id)
#         if result is None:
#             return None
#         if model_class:
#             try:
#                 return model_class(**result)
#             except Exception:
#                 return None
#         return result

#     def find_many(self, collection, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False, limit: Optional[int] = None, filter_dict=None) -> List[T]:
#         logger.info(f"find_many called with filter_dict={filter_dict}, model_class={model_class}, is_canonical={is_canonical}")
#         table = self.db.table(collection)
#         logger.info(f"found with filter_dict={filter_dict}, model_class={model_class}, is_canonical={is_canonical}")
#         if not filter_dict:
#             results = table.all()
#             docs = [doc for doc in results]
#         else:
#             q = Query()
#             logger.info(f"find_many: filter_dict={filter_dict} q: {q}")
#             cond = None
#             for k, v in filter_dict.items():
#                 expr = (q[k] == v)
#                 cond = expr if cond is None else cond & expr
#             results = table.search(cond) if cond is not None else []
#         if model_class:
#             return [model_class(**r) for r in results]
#         return results

#     def find_by_field(self, collection, field, value, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False) -> Optional[T]:
#         table = self.db.table(collection)
#         results = table.search(Query()[field] == value)
#         if model_class:
#             if results:
#                 return model_class(**results[0])
#             return None
#         return results[0] if results else None

#     def find_by_fields(self, collection, fields_dict, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False)-> Optional[T]:
#         table = self.db.table(collection)
#         q = Query()
#         cond = None
#         for k, v in fields_dict.items():
#             expr = (q[k] == v)
#             cond = expr if cond is None else cond & expr
#         results = table.search(cond) if cond is not None else []
#         if model_class:
#             return [model_class(**r) for r in results]
#         return None

#     def update(self, collection, doc_id, updates, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         # Fetch current document and merge updates for check
#         table = self.db.table(collection)
#         current = table.get(Query()[key_field] == doc_id) or {}
#         merged = current.copy()
#         merged.update(updates)
#         logger.info(f"Updating document in collection '{collection}' with id '{doc_id}': updates: {updates}")

#         if not self._check_soft_refs(collection, merged):
#             raise ValueError(f"Soft reference check failed for collection '{collection}' and document: {merged}")
#         return table.update(updates, Query()[key_field] == doc_id)

#     def delete(self, collection, doc_id, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         table = self.db.table(collection)
#         return table.remove(Query()[key_field] == doc_id)

#     def query(self, collection, filter_dict, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False):
#         return self.find_many(collection, filter_dict, model_class, usuario_id, sessao_id, is_canonical)

# # Singleton
# _db_instance = None

# def get_db_instance(db_path=None):
#     global _db_instance
#     if _db_instance is None:
#         _db_instance = TinyDBDatabase(db_path)
#     return _db_instance

# class db:
#     @staticmethod
#     def insert(collection, document, usuario_id=None, sessao_id=None, is_canonical=False):
#         return get_db_instance().insert(collection, document, usuario_id, sessao_id, is_canonical)

#     @staticmethod
#     def find_one(collection, doc_id, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         return get_db_instance().find_one(collection, doc_id, model_class, usuario_id, sessao_id, is_canonical, key_field)

#     @staticmethod
#     def find_many(collection, filter_dict=None, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False):
#         return get_db_instance().find_many(collection, filter_dict, model_class, usuario_id, sessao_id, is_canonical)

#     @staticmethod
#     def find_by_field(collection, field, value, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False):
#         return get_db_instance().find_by_field(collection, field, value, model_class, usuario_id, sessao_id, is_canonical)

#     @staticmethod
#     def find_by_fields(collection, fields_dict, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False):
#         return get_db_instance().find_by_fields(collection, fields_dict, model_class, usuario_id, sessao_id, is_canonical)

#     @staticmethod
#     def update(collection, doc_id, updates, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         return get_db_instance().update(collection, doc_id, updates, usuario_id, sessao_id, is_canonical, key_field)

#     @staticmethod
#     def delete(collection, doc_id, usuario_id=None, sessao_id=None, is_canonical=False, key_field='id'):
#         return get_db_instance().delete(collection, doc_id, usuario_id, sessao_id, is_canonical, key_field)

#     @staticmethod
#     def query(collection, filter_dict, model_class=None, usuario_id=None, sessao_id=None, is_canonical=False):
#         return get_db_instance().query(collection, filter_dict, model_class, usuario_id, sessao_id, is_canonical)

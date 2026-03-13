"""
Constants for Query Engine - MongoDB to SQL operator mappings.

This module defines the mapping between MongoDB query operators and their
SQL equivalents for use in query translation.

MongoDB operators are organized by category:
- Comparison operators ($eq, $ne, $gt, $gte, $lt, $lte, $in, $nin)
- Logical operators ($and, $or, $not, $nor)
- Element operators ($exists, $type)
- Array operators ($all, $elemMatch, $size)
- String operators ($regex, $text)

SQL operators are standard PostgreSQL operators and functions.
"""

from typing import Dict, Set

# MongoDB Comparison Operators
COMPARISON_OPERATORS: Set[str] = {
    "$eq",  # Equal
    "$ne",  # Not equal
    "$gt",  # Greater than
    "$gte",  # Greater than or equal
    "$lt",  # Less than
    "$lte",  # Less than or equal
    "$in",  # In array
    "$nin",  # Not in array
}

# MongoDB Logical Operators
LOGICAL_OPERATORS: Set[str] = {
    "$and",  # Logical AND
    "$or",  # Logical OR
    "$not",  # Logical NOT
    "$nor",  # Logical NOR
}

# MongoDB Element Operators
ELEMENT_OPERATORS: Set[str] = {
    "$exists",  # Field exists
    "$type",  # Field type check
}

# MongoDB Array Operators
ARRAY_OPERATORS: Set[str] = {
    "$all",  # All elements match
    "$elemMatch",  # At least one element matches
    "$size",  # Array size
}

# MongoDB String Operators
STRING_OPERATORS: Set[str] = {
    "$regex",  # Regular expression match
    "$text",  # Text search
}

# All supported MongoDB operators
MONGODB_OPERATORS: Set[str] = (
    COMPARISON_OPERATORS
    | LOGICAL_OPERATORS
    | ELEMENT_OPERATORS
    | ARRAY_OPERATORS
    | STRING_OPERATORS
)

# SQL Operators
SQL_OPERATORS: Dict[str, str] = {
    "$eq": "=",
    "$ne": "!=",
    "$gt": ">",
    "$gte": ">=",
    "$lt": "<",
    "$lte": "<=",
    "$in": "IN",
    "$nin": "NOT IN",
    "$and": "AND",
    "$or": "OR",
    "$not": "NOT",
    "$nor": "NOR",
}

# Operator mapping with SQL templates
OPERATOR_MAPPING: Dict[str, Dict[str, str]] = {
    # Comparison operators
    "$eq": {
        "sql_operator": "=",
        "template": "{field} = {value}",
    },
    "$ne": {
        "sql_operator": "!=",
        "template": "{field} != {value}",
    },
    "$gt": {
        "sql_operator": ">",
        "template": "{field} > {value}",
    },
    "$gte": {
        "sql_operator": ">=",
        "template": "{field} >= {value}",
    },
    "$lt": {
        "sql_operator": "<",
        "template": "{field} < {value}",
    },
    "$lte": {
        "sql_operator": "<=",
        "template": "{field} <= {value}",
    },
    "$in": {
        "sql_operator": "IN",
        "template": "{field} IN ({value})",
    },
    "$nin": {
        "sql_operator": "NOT IN",
        "template": "{field} NOT IN ({value})",
    },
    # Logical operators
    "$and": {
        "sql_operator": "AND",
        "template": "({conditions})",
        "join": " AND ",
    },
    "$or": {
        "sql_operator": "OR",
        "template": "({conditions})",
        "join": " OR ",
    },
    "$not": {
        "sql_operator": "NOT",
        "template": "NOT ({condition})",
    },
    "$nor": {
        "sql_operator": "NOR",
        "template": "NOT ({conditions})",
        "join": " OR ",
    },
    # Element operators
    "$exists": {
        "sql_operator": "IS NULL",
        "template": "{field} IS {not_}NULL",
    },
    "$type": {
        "sql_operator": "pg_typeof",
        "template": "pg_typeof({field}) = {value}",
    },
    # Array operators
    "$all": {
        "sql_operator": "@>",
        "template": "{field} @> {value}",
    },
    "$elemMatch": {
        "sql_operator": "jsonb_path_exists",
        "template": "jsonb_path_exists({field}, {value})",
    },
    "$size": {
        "sql_operator": "jsonb_array_length",
        "template": "jsonb_array_length({field}) = {value}",
    },
    # String operators
    "$regex": {
        "sql_operator": "~",
        "template": "{field} ~ {value}",
    },
    "$text": {
        "sql_operator": "to_tsvector",
        "template": "to_tsvector('english', {field}) @@ plainto_tsquery('english', {value})",
    },
}

# Field type mappings for $type operator
TYPE_MAPPING: Dict[str, str] = {
    "string": "text",
    "number": "numeric",
    "integer": "integer",
    "boolean": "boolean",
    "date": "timestamp",
    "array": "jsonb",
    "object": "jsonb",
    "null": "null",
}

# Reserved SQL keywords that need quoting
RESERVED_KEYWORDS: Set[str] = {
    "select",
    "from",
    "where",
    "and",
    "or",
    "not",
    "in",
    "exists",
    "join",
    "left",
    "right",
    "inner",
    "outer",
    "on",
    "group",
    "by",
    "order",
    "limit",
    "offset",
    "union",
    "intersect",
    "except",
    "insert",
    "update",
    "delete",
    "create",
    "drop",
    "alter",
    "table",
    "index",
    "view",
    "user",
    "role",
    "grant",
    "revoke",
}

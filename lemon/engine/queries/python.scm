; Python Tree-Sitter queries for kiss-py metrics

; --- Functions ---
(function_definition
  name: (identifier) @func.name
  parameters: (parameters) @func.params
  body: (block) @func.body) @func.def

(async_function_definition
  name: (identifier) @func.name
  parameters: (parameters) @func.params
  body: (block) @func.body) @func.def

; --- Classes ---
(class_definition
  name: (identifier) @class.name
  body: (block) @class.body) @class.def

; --- Branches ---
(if_statement) @branch
(elif_clause) @branch
(case_clause) @branch

; --- Returns ---
(return_statement) @return_stmt

; --- Try blocks ---
(try_statement
  body: (block) @try.body)

; --- Calls ---
(call) @call

; --- Imports ---
(import_statement) @import
(import_from_statement) @import

; --- Decorators ---
(decorator) @decorator

; --- Assignments (for local variable counting) ---
(assignment
  left: (identifier) @assignment.target)
(assignment
  left: (pattern_list) @assignment.target)
(augmented_assignment
  left: (identifier) @assignment.target)

; Go Tree-Sitter queries for lemon metrics

; --- Functions ---
(function_declaration
  name: (identifier) @func.name
  parameters: (parameter_list) @func.params
  body: (block) @func.body) @func.def

(method_declaration
  name: (field_identifier) @func.name
  parameters: (parameter_list) @func.params
  body: (block) @func.body) @func.def

; --- Types (structs and interfaces as class equivalents) ---
(type_declaration
  (type_spec
    name: (type_identifier) @class.name
    type: (struct_type
      (field_declaration_list) @class.body))) @class.def

(type_declaration
  (type_spec
    name: (type_identifier) @class.name
    type: (interface_type) @class.body)) @class.def

; --- Branches ---
(if_statement) @branch
(expression_case) @branch
(default_case) @branch
(type_case) @branch
(select_statement) @branch
(communication_case) @branch

; --- Returns ---
(return_statement) @return_stmt

; --- Try equivalent: defer/recover ---
(defer_statement) @try.body

; --- Calls ---
(call_expression) @call

; --- Imports ---
(import_declaration) @import

; --- Assignments (for local variable counting) ---
(short_var_declaration
  left: (expression_list
    (identifier) @assignment.target))
(assignment_statement
  left: (expression_list
    (identifier) @assignment.target))
(var_declaration
  (var_spec
    name: (identifier) @assignment.target))

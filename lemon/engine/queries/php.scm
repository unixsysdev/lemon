; PHP Tree-Sitter queries for kiss-py metrics

; --- Functions ---
(function_definition
  name: (name) @func.name
  parameters: (formal_parameters) @func.params
  body: (compound_statement) @func.body) @func.def

(method_declaration
  name: (name) @func.name
  parameters: (formal_parameters) @func.params
  body: (compound_statement) @func.body) @func.def

; --- Classes ---
(class_declaration
  name: (name) @class.name
  body: (declaration_list) @class.body) @class.def

(interface_declaration
  name: (name) @interface.name) @interface.def

; --- Branches ---
(if_statement) @branch
(else_if_clause) @branch
(case_statement) @branch

; --- Returns ---
(return_statement) @return_stmt

; --- Try blocks ---
(try_statement
  body: (compound_statement) @try.body)

; --- Calls ---
(function_call_expression) @call
(member_call_expression) @call
(scoped_call_expression) @call

; --- Imports (use statements / require / include) ---
(namespace_use_declaration) @import
(expression_statement
  (include_expression)) @import
(expression_statement
  (include_once_expression)) @import

; --- Attributes (PHP 8+) ---
(attribute_group) @decorator

; --- Assignments ---
(assignment_expression
  left: (variable_name) @assignment.target)
(augmented_assignment_expression
  left: (variable_name) @assignment.target)

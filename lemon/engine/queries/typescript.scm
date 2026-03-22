; TypeScript Tree-Sitter queries for kiss-py metrics

; --- Functions ---
(function_declaration
  name: (identifier) @func.name
  parameters: (formal_parameters) @func.params
  body: (statement_block) @func.body) @func.def

(generator_function_declaration
  name: (identifier) @func.name
  parameters: (formal_parameters) @func.params
  body: (statement_block) @func.body) @func.def

; Arrow functions
(arrow_function
  parameters: (formal_parameters) @func.params
  body: (statement_block) @func.body) @func.def

; Method definitions in classes
(method_definition
  name: (property_identifier) @func.name
  parameters: (formal_parameters) @func.params
  body: (statement_block) @func.body) @func.def

; --- Classes ---
(class_declaration
  name: (type_identifier) @class.name
  body: (class_body) @class.body) @class.def

; --- Interfaces (TypeScript-specific) ---
(interface_declaration
  name: (type_identifier) @interface.name) @interface.def

; --- Type aliases (TypeScript-specific) ---
(type_alias_declaration
  name: (type_identifier) @type_alias.name) @type_alias.def

; --- Branches ---
(if_statement) @branch
(switch_case) @branch

; --- Returns ---
(return_statement) @return_stmt

; --- Try blocks ---
(try_statement
  body: (statement_block) @try.body)

; --- Calls ---
(call_expression) @call
(new_expression) @call

; --- Imports ---
(import_statement) @import

; --- Decorators (TypeScript experimental decorators) ---
(decorator) @decorator

; --- Assignments ---
(variable_declarator
  name: (identifier) @assignment.target)
(assignment_expression
  left: (identifier) @assignment.target)
(augmented_assignment_expression
  left: (identifier) @assignment.target)

{# Convert an integer-cents column to BRL reais with 2 decimals. #}
{% macro cents_to_reais(column_name) %}
    round({{ column_name }} / 100.0, 2)
{% endmacro %}

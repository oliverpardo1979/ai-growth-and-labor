# Integración de la extensión laboral

`static_equilibrium.tex` especifica el equilibrio extendido y resuelve la asignación estática con trabajo sectorial y capital móvil. Mantiene la ley de investigación del manuscrito, la propiedad conjunta del capital y del desarrollador por el hogar representativo, y un proveedor monopolístico común sin discriminación de precios. No modifica el texto activo del paper.

Resultados establecidos en la nota:

- La asignación de capital reduce la producción a K^alpha (Z_S+Z_C)^(1-alpha).
- La oferta total de IA se asigna mediante un precio sombra común entre las actividades activas. La actividad complementaria puede estar cerrada cuando el total ofrecido es bajo.
- Existe un máximo monopolístico global positivo y finito. Se ofrece una parametrización escalar del objetivo para compararlo globalmente.
- La condición de primer orden no selecciona por sí sola el óptimo. En el ejemplo registrado hay dos máximos locales de distinto beneficio.
- La provisión competitiva tiene una única cantidad positiva. El monopolio reduce la oferta total a igual capital, dotaciones y eficiencia.

`check_joint_supply.py` comprueba las derivadas de la demanda inversa, la agregación de capital y el ejemplo de dos máximos locales. `joint_supply_checks.json` conserva el resultado PASS. No es una simulación de equilibrio ni una demostración de multiplicidad del óptimo global.

Pendientes: regularidad y selección global cerca de los límites, óptimo de investigación y existencia dinámica, y solución de la asignación con movilidad laboral. Las notas competitivas de la otra rama no se consideran una prueba del equilibrio monopolístico.

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

## Segundo avance

`long_run_selection.tex` establece que todos los máximos globales convergen a la misma oferta por unidad de capital cuando K/(AN) diverge y B converge a un valor finito positivo. Además, el máximo es único para capital suficientemente alto. La prueba localiza todos los máximos mediante cotas globales y utiliza convergencia de las dos primeras derivadas en un entorno del máximo límite. No depende de escoger el mayor máximo encontrado en una cuadrícula.

El precio límite es 1/[B_infinito(1-alpha)]. Con C/K convergente positivo y crecimiento g del producto por trabajador superior a gamma, se recuperan bajo monopolio las tasas medias g_wS=gamma+(g-gamma)/sigma_S y g_wC=gamma. Son resultados condicionales a la trayectoria, no existencia demostrada.

Una proposición adicional muestra que B_infinito=Bbar dentro de un equilibrio acelerado regular con costate no negativo y óptimo normal diferenciable del desarrollador. El argumento compara el límite inferior q>=aK obtenido del costate con M=O(K) exigido por recursos. No convierte condiciones necesarias en suficientes.

`check_long_run_selection.py` compara candidatos estáticos globales a intensidades de capital crecientes en dos configuraciones. `long_run_checks.json` registra PASS. Los valores elevados de K/H son comprobaciones de límites, no una calibración ni una predicción de fechas.

Pendientes actuales: construir trayectorias de equilibrio y verificar el óptimo global intertemporal. La movilidad laboral también sigue pendiente. El manuscrito activo permanece sin cambios.

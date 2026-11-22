# Automatización endógena — exploración separada

Fecha de inicio: 22 de noviembre de 2026.

Este directorio contiene una exploración del margen extensivo de automatización. No modifica ni sustituye el manuscrito `ai-growth-and-labor/main_rewrite.tex`. No se han ejecutado transiciones de equilibrio ni publicado resultados.

## Primera especificación

Una masa unitaria de tareas se agrega con una CES de elasticidad sigma. Cada tarea puede producirse con trabajo humano o con servicios de IA, sustitutos perfectos dentro de la tarea. La productividad humana por unidad efectiva es uno y la productividad de la IA en la tarea i es exp(-beta i), beta>0. La IA puede ejecutar todas las tareas desde el inicio, pero no necesariamente a un costo competitivo. Esta primera especificación endogeneiza la adopción económica, no una restricción de factibilidad tecnológica.

El producto final es Y=K^alpha Z^(1-alpha). H=AL y X=BU. La movilidad del trabajo entre tareas y su homogeneidad se mantienen como punto de partida. No se modelan ocupaciones, desigualdad entre trabajadores ni costos de reasignación.

## Resultados derivados

1. Para H,X>0 existe una única partición eficiente con IA en [0,m] y humanos en (m,1], salvo la tarea marginal, de medida cero. La asignación se obtiene mediante precios de soporte y es globalmente eficiente por concavidad.
2. D_sigma(m)=integral_0^m exp[-beta(sigma-1)i] di y X/H=D_sigma(m)exp(sigma beta m)/(1-m). El lado derecho es estrictamente creciente, de cero a infinito.
3. La condición de costo en la tarea marginal da w/(A p_X)=exp(beta m). Por tanto el salario relativo a A p_X está acotado entre 1 y exp(beta). Este resultado contrasta con la división fija de tareas del paper original.
4. Cuando X/H tiende a infinito, Z/X y Z_X convergen a c_sigma>0 para CUALQUIER sigma>0, con c_sigma=[integral_0^1 exp(-beta(sigma-1)i)di]^(1/(sigma-1)), y c_1=exp(-beta/2). No se requiere sigma>1 para una tecnología asintóticamente lineal porque ninguna tarea está permanentemente reservada a humanos.
5. Con K,H,B fijos y provisión competitiva, hay adopción positiva si y solo si B(1-alpha)(K/H)^alpha>1. La demanda marginal de IA en X=0 es finita. La oferta monopolística tiene el mismo criterio de entrada positivo y, cuando es positiva, restringe X y m respecto a competencia a igual K,H,B. La unicidad del máximo monopolístico no está demostrada.
6. Con competencia y adopción interior, w=A exp(beta m)/B. Si B permanece acotado y converge a un valor positivo, la tasa MEDIA de crecimiento del salario converge a gamma, incluso si el producto crece más rápido. Si las tasas instantáneas convergen, su límite coincide con esa tasa media. No confundir convergencia de niveles con convergencia de derivadas.
7. Para un monopolista de precio uniforme que toma K,H como dados, la elasticidad inversa de demanda converge a alpha cuando X/H diverge. Condicional a una trayectoria de equilibrio con ese límite y B->Bbar finito, el markup converge a 1/(1-alpha), p_X->1/[Bbar(1-alpha)] y el crecimiento salarial medio vuelve a gamma.
8. El rendimiento límite candidato del capital conserva la estructura del original, reemplazando omega_X^(sigma/(sigma-1)) por c_sigma. Esto no demuestra existencia, convergencia, optimalidad intertemporal ni comparaciones de bienestar.
9. Si ambas trayectorias existen y X/H diverge bajo competencia (B=B0) y monopolio (B->Bbar), con las mismas tareas y el mismo A, w_mon/w_mc converge a B0/[(1-alpha)Bbar]. El monopolio tiene mayor rendimiento límite del capital exactamente cuando esa razón salarial es menor que uno. Es una comparación de niveles salariales relativos, no de tasas de crecimiento salarial ni de bienestar. La existencia de ambas trayectorias desde un estado común queda pendiente.

## Verificación

`check_task_block.py` verifica identidades, derivadas, asignación por tareas y límites en 42 casos estáticos. `static_checks.json` registra resultados. No son simulaciones de transición. Las diferencias finitas verifican las expresiones, no sustituyen sus pruebas.

La primera comprobación de la derivada respecto a H sufrió cancelación numérica al reoptimizar una frontera casi igual a uno. Se reemplazó por la diferencia finita del valor de la partición fija en la solución candidata, como permite el teorema de la envolvente. El error relativo máximo resultante fue inferior a 4e-7. No se relajaron tolerancias para obtener PASS.

## Conexión con el original

Se conservan utilidad logarítmica, acumulación de K, X=BU y el costo de compute. Como benchmark se conserva también Bbar y la ley de investigación original. No se introduce una fecha exógena de activación. Investigación positiva desde una fecha inicial es una propiedad que debe verificarse, no imponerse mediante las condiciones interiores.

Con demanda inversa P(X;K,H), el desarrollador elige pi(B)=max_X[P(X;K,H)X-X/B]. Si se cumplen las hipótesis de envolvente, pi_B=X/B^2 como en el original. Se mantienen la estructura de la ecuación de costo de investigación y el costate, pero NO se transfieren las condiciones suficientes de optimalidad global ni las pruebas de existencia del paper.

El desarrollador sigue tomando K y r como dados. La objeción del referee 2 sobre realimentación estratégica y compromiso sigue pendiente.

## Lectura económica

Permitir la automatización de tareas adicionales puede preservar el mecanismo agregado tipo AK y modificar el resultado salarial. Esto es un resultado de esta especificación con ventaja relativa de IA acotada y tareas completamente automatizables, no una conclusión general de cualquier modelo de tareas.

## Pendientes antes de resolver transiciones

- Verificar originalidad frente a Korinek–Suh y Jones–Tonetti. No reclamar novedad por obtener una frontera o perder la prima salarial.
- Demostrar o refutar unicidad y regularidad de la oferta monopolística global.
- Establecer optimalidad global del problema de investigación y existencia dinámica desde estados iniciales explícitos.
- Examinar una distribución no acotada de dificultad relativa y/o tareas no automatizables. No elegir la distribución solo para restaurar el resultado salarial anterior.
- Distinguir adopción económica de una frontera tecnológica de nuevas capacidades.
- Decidir si la automatización de la investigación también debe ser endógena. No queda endogeneizada por automatizar tareas de producción.
- Resolver condiciones terminales propias antes de adaptar el solver del paper.

## Referencias iniciales por verificar en detalle

- Acemoglu, Daron y Pascual Restrepo (2019), Automation and New Tasks: How Technology Displaces and Reinstates Labor, Journal of Economic Perspectives 33(2), 3–30. https://doi.org/10.1257/jep.33.2.3
- Korinek, Anton y Donghyun Suh (2024), Scenarios for the Transition to AGI, NBER Working Paper 32255. https://www.nber.org/papers/w32255
- Jones, Charles I. y Christopher Tonetti, Past Automation and Future AI: How Weak Links Tame the Growth Explosion. Verificar la versión vigente antes de atribuir resultados. https://christophertonetti.com/research.html

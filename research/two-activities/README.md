# Dos actividades con distinta sustitución entre trabajo e IA

Rama exploratoria creada el 22 de noviembre de 2026 desde el estado local del paper original. No cambia el manuscrito ni hereda los archivos de la rama de automatización de tareas. Esta es una propuesta de entorno, no un equilibrio resuelto.

## Producción

Dos actividades j en {S,C} producen Y_j=K_j^alpha Z_j^(1-alpha). En cada actividad:

Z_j=[omega_Lj (A L_j)^((sigma_j-1)/sigma_j)+omega_Xj X_j^((sigma_j-1)/sigma_j)]^(sigma_j/(sigma_j-1)),

con 0<sigma_C<1<sigma_S. La elasticidad sigma_j es entre trabajo efectivo e IA dentro de la actividad j, no entre actividades. Cada Z_j es un agregado de insumos, no una tarea elemental.

X_j=B U_j. La eficiencia B es común en el benchmark. No se ha decidido si mantener B fijo para aislar la heterogeneidad o añadir después investigación. No se han introducido dos tecnologías de investigación.

El capital físico es móvil y acumulable, con K_S+K_C=K. En una asignación interior, los productos marginales del capital, valorados a los precios de los bienes, son iguales.

## Agregación de actividades

Con un único bien y actividades que son formas alternativas de producirlo, Y=Y_S+Y_C. Si ambas tienen el mismo alpha y no hay fricciones en la asignación de capital, la asignación óptima implica K_j/K=Z_j/(Z_S+Z_C) y Y=K^alpha (Z_S+Z_C)^(1-alpha). La suma no es una decisión inocente: no exige que ambas actividades sigan activas.

Si ambas actividades producen componentes distintos del bien final, usar una CES Y=[theta Y_S^((tau-1)/tau)+(1-theta)Y_C^((tau-1)/tau)]^(tau/(tau-1)). Tau mide sustitución ENTRE actividades. Debe distinguirse de sigma_S y sigma_C. La elección entre estas agregaciones sigue abierta.

## Asignación de trabajadores

Para estudiar ingresos distintos, no basta con dos actividades y trabajadores idénticos perfectamente móviles. En ese benchmark, los salarios por trabajador se igualan si ambas actividades emplean trabajo.

Una extensión parsimoniosa es que cada trabajador i tenga eficiencias (e_S(i),e_C(i)). Entonces L_j es la suma de eficiencias de quienes trabajan en j. Si v_j es la remuneración por unidad de eficiencia laboral, un trabajador sin costos de movilidad elige la actividad que maximiza v_j e_j(i). La ventaja comparativa genera selección entre actividades, pero no es un costo de movilidad. Los costos de cambiar de actividad, si se necesitan, deben añadirse explícitamente y requieren especificar historia y decisiones intertemporales.

El primer benchmark puede fijar las dotaciones de ambos tipos laborales para aislar los efectos de capital móvil. Posteriormente se permite reasignación por ventaja comparativa. Ninguno de estos cierres se presenta aún como una decisión definitiva.

## Hogar, recursos y proveedor de IA

Se puede conservar la utilidad intertemporal del paper original y un único bien de consumo e inversión. La restricción de recursos es C+dot K+delta K+U_S+U_C+M=Y, con M=0 si se fija la tecnología y no hay investigación.

La oferta competitiva de servicios de IA o su provisión por un monopolista común deben especificarse por separado. Con monopolio, también debe decidirse si el proveedor cobra un precio uniforme o discrimina entre actividades. No se ha resuelto esa decisión ni el equilibrio.

## Pregunta

Cómo la expansión de IA y la acumulación de capital afectan salarios y asignación del trabajo cuando unas actividades presentan complementariedad y otras sustitución. No se supone de antemano qué grupo gana, ni que capital móvil garantice ganancias salariales para el grupo expuesto a sustitución.

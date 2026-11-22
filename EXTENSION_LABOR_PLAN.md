# Labor Heterogeneity and Reallocation

Rama de integración: `extension/labor-heterogeneity-reallocation`.

## Alcance y punto de partida

Agregar una sección breve al paper existente para determinar qué resultados de crecimiento y salarios sobreviven con dos actividades, una con complementariedad y otra con sustitución entre trabajo e IA. Ambas producen el mismo bien final, Y=Y_C+Y_S. La sustitución perfecta entre productos debe aparecer explícitamente como supuesto.

La rama reúne el estado local `71cd3e8` y el estado remoto `df46bbd`, conservando los cambios no solapados. No modifica `main`. Las notas previas permanecen en `research/two-activities-heterogeneity`, commit `9de2983`. No se incorporan automáticamente como texto del paper ni se importa la rama del modelo de tareas.

Título, abstract, introducción, Related Literature y conclusiones siguen cerrados. Se reportará cualquier ajuste de conexión necesario antes de modificar esas secciones. La edición digital pública no se actualiza mientras la extensión permanezca en desarrollo.

## 1. Fijar el entorno con la notación del paper

Leer las definiciones vigentes del modelo y del equilibrio y las pruebas relevantes. Definir Y_j=K_j^alpha Z_j^(1-alpha), con 0<sigma_C<1<sigma_S, capital móvil, eficiencia B común y X_j=B U_j. Mantener el hogar representativo con las dos dotaciones laborales e ingresos agrupados, salvo que un resultado exija otro cierre. No introducir desigualdad patrimonial ni costos de movilidad nuevos.

Separar dos casos de oferta laboral. En el primero, cada tipo está vinculado a una actividad y sus participaciones poblacionales son positivas y fijas. En el segundo, los trabajadores son idénticos y pueden reasignarse libremente. La ventaja comparativa individual y los costos de cambiar de actividad quedan fuera de esta extensión mínima.

Entregable: entorno y definición del equilibrio extendido, con una lista de supuestos nuevos y otra de supuestos conservados. Verificar las restricciones de recursos, incluida la investigación si se mantiene RSI.

## 2. Resolver la asignación estática y la oferta de IA

Demostrar la agregación Y=K^alpha (Z_C+Z_S)^(1-alpha) después de asignar capital. Derivar precios, salarios y demandas de IA, incluidas las esquinas y el cierre de una actividad.

Comenzar por el proveedor monopolístico del paper, con un precio común como benchmark explícito. Precisar qué variables toma como dadas y qué margen de reasignación incorpora su demanda inversa. Resolver el máximo global, no solo sus condiciones de primer orden. Comparar después con provisión competitiva. No introducir discriminación de precios silenciosamente.

Entregable: bloque estático consistente con la estructura de mercado del manuscrito. Las fórmulas competitivas existentes son una comprobación inicial, no una solución del monopolio.

## 3. Establecer los resultados asintóticos con trabajo sectorial

Reconstruir el candidato dominado por IA y comprobar si B converge a Bbar, qué rendimiento sostiene el crecimiento y qué ocurre con la investigación y las condiciones de transversalidad. Distinguir identidades condicionales de existencia de trayectorias que las satisfagan.

Verificar o corregir los candidatos g_wS=gamma+(g-gamma)/sigma_S y g_wC=gamma, la participación de cada actividad y las dos participaciones laborales. Comprobar también el régimen con crecimiento a gamma. No presentar diferencias de crecimiento como ganancias de nivel o bienestar.

Entregable: un enunciado breve y su prueba. Si no se consigue existencia para el modelo extendido, declarar con precisión el alcance condicional, sin atribuirle la prueba de existencia del modelo original.

## 4. Resolver la reasignación laboral

Usar igualdad salarial cuando ambas actividades emplean trabajadores y las desigualdades apropiadas en las esquinas. Comprobar si la concentración del trabajo en S ocurre en fecha finita, solo asintóticamente o no se sigue bajo algún supuesto. No inferir desaparición exacta de C de una participación que converge a cero.

Determinar en qué sentido se recupera el resultado original. La recuperación tecnológica en el límite no prueba por sí sola optimalidad del desarrollador ni existencia de una trayectoria de equilibrio.

Entregable: corolario, proposición o discusión, según la fuerza del resultado demostrado. Mantener separados los casos de trabajo sectorial y trabajo móvil.

## 5. Comprobación teórica y bibliográfica focalizada

Comprobar hipótesis, casos frontera, equilibrio de ambos sectores y dependencias de las demostraciones. Usar verificaciones simbólicas o estáticas para detectar errores, sin sustituir la prueba. Buscar antecedentes sobre heterogeneidad laboral, cambio estructural y automatización solo para las atribuciones necesarias. No reabrir toda la literatura.

Entregable: registro de resultados demostrados, condicionales y pendientes. Un problema sustantivo se resuelve o se comunica antes de redactar como si estuviera cerrado.

## 6. Integración editorial mínima

Título previsto: **Labor Heterogeneity and Reallocation**. Subsecciones previstas: **Sector-Specific Labor** y **Mobile Labor**. La ubicación provisional es después de los resultados de monopolio y competencia y antes de las simulaciones. Confirmarla con la estructura efectiva del manuscrito.

Presentar pregunta, entorno mínimo, resultado, intuición y alcance de la agregación aditiva. Enviar cálculos y pruebas al apéndice. No añadir simulaciones salvo que respondan una pregunta que la teoría no resuelva. No cambiar las simulaciones existentes.

Entregable: sección legible por sí misma con las referencias internas necesarias, sin repetir el modelo completo ni describirla como robustez a cualquier heterogeneidad.

## 7. Verificación y publicación

Compilar el manuscrito y el suplemento, comprobar referencias cruzadas y revisar los pasajes vecinos a la nueva sección. Mantener commits acotados en esta rama. Preparar y validar la versión digital correspondiente cuando el contenido esté cerrado.

La integración a `main` y la publicación pública se hacen después de revisar la extensión, no como efecto automático de subir esta rama. En ese momento se sigue el protocolo del repositorio para PDF, suplemento y edición digital.

## Próxima tarea

Primer avance de los pasos 1 y 2 documentado en `research/labor-extension/static_equilibrium.tex`. Se especificaron el hogar, los cierres laborales y el equilibrio extendido. Para trabajo sectorial se derivaron la asignación conjunta, la demanda inversa y la existencia de un máximo global positivo y finito del proveedor. La condición de primer orden no basta: un ejemplo con sigma_C=0.25 tiene dos máximos locales. No se ha afirmado multiplicidad de máximos globales.

Segundo avance documentado en `research/labor-extension/long_run_selection.tex`. Se establece selección global única y suave para capital suficientemente alto respecto al trabajo efectivo, con B cerca de un límite finito positivo. Se derivan las tasas salariales condicionales bajo monopolio. También se prueba que B debe alcanzar Bbar dentro de un equilibrio acelerado regular con el costate y las condiciones necesarias explícitamente indicados.

La próxima tarea es construir las trayectorias y verificar optimalidad global intertemporal, distinguiendo ambas obligaciones. El problema de asignación con trabajo móvil también sigue pendiente. No se ha insertado todavía una sección en el manuscrito.

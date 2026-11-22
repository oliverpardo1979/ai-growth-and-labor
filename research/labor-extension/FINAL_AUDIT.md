# Auditoría final de la extensión

## Veredicto y alcance

Los enunciados y sus pruebas sostienen la caracterización condicional indicada. No se afirma existencia dinámica, optimalidad global intertemporal obtenida a partir de condiciones de primer orden, ganancias de bienestar o mejoras salariales en todas las fechas. La adopción de productos perfectamente sustituibles, capital móvil, eficiencia común y precio uniforme de IA permanece explícita.

## Comprobaciones decisivas

1. La asignación de capital iguala K_j/Z_j y permite usar la suma de composites. No se mantienen capitales sectoriales fijos al calcular la demanda conjunta de IA.
2. La provisión monopolística se selecciona globalmente. La existencia de varios máximos locales fuera del límite no invalida la comparación compacta que identifica la oferta límite.
3. La convergencia uniforme del objetivo normalizado se obtiene de la expansión CES y de la cantidad complementaria acotada. Se añadieron esas cotas a la prueba para no dejar esa justificación implícita.
4. Con trabajo sectorial, X_C/(A L_C) y w_C/A convergen a constantes positivas. Z_S domina el agregado. El Euler y C/K convergente positivo justifican las tasas medias de producto y salarios. No se infiere convergencia de derivadas de la convergencia de niveles.
5. Con trabajo móvil, Z_C<=b_L H_C y la concavidad de Z_S comparan cualquier reparto con la asignación íntegra a S. Por encima del umbral suficiente, toda asignación con H_C>0 es estrictamente inferior. Si H_C=0 y X_C>0, la IA se desperdicia. La reasignación de capital completa el cierre de C.
6. El argumento de selección global implica X/K con límite positivo también con trabajo móvil. Junto con K/(AN) divergente, esto hace que X/(AN) supere permanentemente el umbral después de una fecha finita. No se confunde una cuota tendiendo a cero con cierre exacto.

Confianza High en las identidades y en el argumento global de reasignación bajo los supuestos declarados. La existencia del equilibrio no fue auditada ni demostrada, por el alcance acordado.

## Comprobaciones estáticas ejecutadas

- `check_joint_supply.py`: demanda, asignación de capital y ejemplo de dos máximos locales.
- `check_long_run_selection.py`: comparación de candidatos y límites estáticos en dos configuraciones.
- `check_mobile_labor.py`: cota global y umbral suficiente en seis combinaciones de elasticidades.

Los tres scripts registran PASS. No son simulaciones dinámicas ni sustituyen las pruebas.

## Comprobación bibliográfica focalizada

Hémous y Olsen (2022), *The Rise of the Machines: Automation, Horizontal Innovation, and Income Inequality*, AEJ: Macroeconomics 14(1), 179–223, DOI https://doi.org/10.1257/mac.20160164. Se cotejaron el texto introductorio publicado y la especificación de producción de la sección I.A, pp.182–183, ecuaciones1–2. Los grupos son trabajo de alta y baja habilidad, y la máquina sustituye trabajo de baja habilidad dentro de una tecnología que también utiliza trabajo de alta habilidad. No es el mismo modelo que dos actividades con productos perfectamente sustituibles. Se reutiliza la cita ya existente para delimitar esa diferencia, sin atribuir novedad general a salarios crecientes o brechas salariales.

Hutschenreiter, Santini y Vella (2022), *Automation and sectoral reallocation*, SERIEs 13, 335–362, DOI https://doi.org/10.1007/s13209-021-00240-w. Se consultaron el planteamiento y la discusión de elasticidades en la versión editorial HTML. Es un antecedente relacionado de automatización y reasignación con bienes sectoriales distintos y fricciones de búsqueda. No se auditó su álgebra ni se utiliza para respaldar nuestros enunciados. No se añade una cita decorativa a una sección que no pretende revisar esa literatura.

La búsqueda no constituye una certificación de originalidad de todos los resultados. La extensión no hace tal afirmación.

## Cambios editoriales aprobados

- Párrafo de organización de la introducción: ocho secciones y referencia a la extensión.
- Related Literature: solo sustituir «In this paper» por «In the baseline model» en la frase sobre ausencia de heterogeneidad laboral. Oliver autorizó expresamente ese cambio.
- Corolario: precisar L_S=N y L_C=K_C=X_C=0, evitando que «productive inputs» pudiera incluir investigación.

Se conservan título, abstract, resto de introducción y literatura, y conclusiones. La publicación requiere PDF, suplemento y snapshot digital validados de los mismos fuentes.

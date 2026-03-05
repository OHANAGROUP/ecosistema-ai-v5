/**
 * CALCULADOR DE RENDIMIENTO ALPA - PARTIDA CERÁMICA
 * Este módulo procesa m2 y devuelve la lista de materiales optimizada.
 */

function calcularMateriales(m2) {
    const area = parseFloat(m2);
    if (isNaN(area) || area <= 0) return null;

    // 1. Cerámica (m2 + 10% de pérdida/cortes)
    const ceramicaFinal = area * 1.10;

    // 2. Adhesivo (Pegamento: rinde aprox 4m2 por saco de 25kg)
    const sacosAdhesivo = Math.ceil(area / 4);

    // 3. Fragüe (Rinde aprox 1kg por cada 3m2)
    const kgFrague = Math.ceil(area / 3);

    return {
        inputArea: area,
        materiales: [
            { item: "Cerámica / Porcelanato", cantidad: ceramicaFinal.toFixed(2), unidad: "m²", detalle: "Incluye 10% de pérdida" },
            { item: "Adhesivo Cerámico (Sacos 25kg)", cantidad: sacosAdhesivo, unidad: "Sacos", detalle: "Rendimiento 4m²/saco" },
            { item: "Fragüe (KG)", cantidad: kgFrague, unidad: "kg", detalle: "Calculado a 1kg/3m²" }
        ],
        timestamp: new Date().toISOString()
    };
}

// Para ejecución vía consola
if (require.main === module) {
    const areaTest = process.argv[2] || 25;
    console.log("--- SIMULACIÓN DE CÁLCULO ALPA ---");
    console.log(`Área base: ${areaTest} m²`);
    const resultado = calcularMateriales(areaTest);
    console.table(resultado.materiales);
}

module.exports = { calcularMateriales };

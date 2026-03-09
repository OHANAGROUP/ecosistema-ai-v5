/**
 * CALCULADOR DE RENDIMIENTO ALPA - PARTIDA CERÃMICA
 * Este mÃ³dulo procesa m2 y devuelve la lista de materiales optimizada.
 */

function calcularMateriales(m2) {
    const area = parseFloat(m2);
    if (isNaN(area) || area <= 0) return null;

    // 1. CerÃ¡mica (m2 + 10% de pÃ©rdida/cortes)
    const ceramicaFinal = area * 1.10;

    // 2. Adhesivo (Pegamento: rinde aprox 4m2 por saco de 25kg)
    const sacosAdhesivo = Math.ceil(area / 4);

    // 3. FragÃ¼e (Rinde aprox 1kg por cada 3m2)
    const kgFrague = Math.ceil(area / 3);

    return {
        inputArea: area,
        materiales: [
            { item: "CerÃ¡mica / Porcelanato", cantidad: ceramicaFinal.toFixed(2), unidad: "mÂ²", detalle: "Incluye 10% de pÃ©rdida" },
            { item: "Adhesivo CerÃ¡mico (Sacos 25kg)", cantidad: sacosAdhesivo, unidad: "Sacos", detalle: "Rendimiento 4mÂ²/saco" },
            { item: "FragÃ¼e (KG)", cantidad: kgFrague, unidad: "kg", detalle: "Calculado a 1kg/3mÂ²" }
        ],
        timestamp: new Date().toISOString()
    };
}

// Para ejecuciÃ³n vÃ­a consola
if (require.main === module) {
    const areaTest = process.argv[2] || 25;
    console.log("--- SIMULACIÃ“N DE CÃLCULO ALPA ---");
    console.log(`Ãrea base: ${areaTest} mÂ²`);
    const resultado = calcularMateriales(areaTest);
    console.table(resultado.materiales);
}

module.exports = { calcularMateriales };

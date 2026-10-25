// Okapi Wildlife Reserve mining / forest-change screening, 2000–2026.
// Run in the Google Earth Engine Code Editor after setting the asset IDs below.
// This maps candidate forest-to-bare transitions; it does not classify mines.

var CONFIG = {
  reserveAsset: 'projects/REPLACE_WITH_YOUR_PROJECT/assets/okapi_reserve_boundary',
  miningSitesAsset: '', // Optional verified mine polygons/points; leave blank if unavailable.
  firstYear: 2000,
  lastYear: 2026,
  bufferMeters: 10000,
  mineProximityMeters: 500,
  analysisScaleMeters: 30,
  targetCrs: 'EPSG:32635',
  cloudCoverMax: 80
};
var HANSEN_GFC = ee.Image('UMD/hansen/global_forest_change_2024_v1_12');

var reserveFeatures = ee.FeatureCollection(CONFIG.reserveAsset);
var reserve = reserveFeatures.geometry(1);
var bufferOuter = reserve.buffer(CONFIG.bufferMeters, 1);
var bufferRing = bufferOuter.difference(reserve, 1);
var zones = ee.FeatureCollection([
  ee.Feature(reserve, {zone: 'Reserve'}),
  ee.Feature(bufferRing, {zone: 'Buffer_0_10km'})
]);
var hasMiningInventory = CONFIG.miningSitesAsset !== '';
var miningSites = hasMiningInventory
  ? ee.FeatureCollection(CONFIG.miningSitesAsset)
  : ee.FeatureCollection([]);

Map.centerObject(reserveFeatures, 8);

function maskLandsat(image) {
  var qa = image.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 0).eq(0)
    .and(qa.bitwiseAnd(1 << 1).eq(0))
    .and(qa.bitwiseAnd(1 << 3).eq(0))
    .and(qa.bitwiseAnd(1 << 4).eq(0))
    .and(qa.bitwiseAnd(1 << 5).eq(0));
  return image.updateMask(clear).updateMask(image.select('QA_RADSAT').eq(0));
}

function landsatIndices(image, sensor) {
  var sourceBands = sensor === 'L57'
    ? ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    : ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'];
  var reflectance = maskLandsat(image)
    .select(sourceBands, ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
    .multiply(0.0000275)
    .add(-0.2);
  return addIndices(reflectance).copyProperties(image, ['system:time_start']);
}

function sentinel2Indices(image) {
  var scl = image.select('SCL');
  var clear = scl.neq(0).and(scl.neq(1)).and(scl.neq(3))
    .and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  var reflectance = image.updateMask(clear)
    .select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12'],
      ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
    .multiply(0.0001);
  return addIndices(reflectance).copyProperties(image, ['system:time_start']);
}

function addIndices(image) {
  var ndvi = image.normalizedDifference(['nir', 'red']).rename('ndvi');
  var nbr = image.normalizedDifference(['nir', 'swir2']).rename('nbr');
  var mndwi = image.normalizedDifference(['green', 'swir1']).rename('mndwi');
  var bsi = image.expression(
    '((swir1 + red) - (nir + blue)) / ((swir1 + red) + (nir + blue))',
    {
      swir1: image.select('swir1'),
      red: image.select('red'),
      nir: image.select('nir'),
      blue: image.select('blue')
    }
  ).rename('bsi');
  return ee.Image.cat([ndvi, nbr, mndwi, bsi])
    .copyProperties(image, ['system:time_start']);
}

var landsat5 = ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.lte('CLOUD_COVER', CONFIG.cloudCoverMax))
  .map(function (image) { return landsatIndices(image, 'L57'); });
var landsat7 = ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.lte('CLOUD_COVER', CONFIG.cloudCoverMax))
  .map(function (image) { return landsatIndices(image, 'L57'); });
var landsat8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.lte('CLOUD_COVER', CONFIG.cloudCoverMax))
  .map(function (image) { return landsatIndices(image, 'L89'); });
var landsat9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.lte('CLOUD_COVER', CONFIG.cloudCoverMax))
  .map(function (image) { return landsatIndices(image, 'L89'); });
var sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', CONFIG.cloudCoverMax))
  .map(sentinel2Indices);

var optical = landsat5.merge(landsat7).merge(landsat8).merge(landsat9).merge(sentinel2);
var opticalSensors = [landsat5, landsat7, landsat8, landsat9, sentinel2];

function annualOptical(year) {
  year = ee.Number(year);
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var emptyIndices = ee.Image.constant([0, 0, 0, 0])
    .rename(['ndvi', 'nbr', 'mndwi', 'bsi'])
    .updateMask(ee.Image.constant(0));
  var perSensor = ee.ImageCollection.fromImages(opticalSensors.map(function (sensor) {
    var scenes = ee.ImageCollection(sensor).filterDate(start, end);
    var composite = ee.Image(ee.Algorithms.If(
      scenes.size().gt(0),
      scenes.median().select(['ndvi', 'nbr', 'mndwi', 'bsi']),
      emptyIndices
    ));
    return composite.set('scene_count', scenes.size());
  }));
  var indices = perSensor.median();
  var collection = optical.filterDate(start, end);
  var observations = ee.Image(ee.Algorithms.If(
    collection.size().gt(0),
    collection.select('ndvi').count().rename('observations'),
    ee.Image.constant(0).rename('observations')
  ));
  return indices.addBands(observations)
    .clip(bufferOuter)
    .set('year', year)
    .set('scene_count', perSensor.aggregate_sum('scene_count'))
    .set('system:time_start', start.millis());
}

var annual = ee.ImageCollection.fromImages(
  ee.List.sequence(CONFIG.firstYear - 1, CONFIG.lastYear).map(annualOptical)
);
var baseline = ee.Image(annual.filter(ee.Filter.eq('year', CONFIG.firstYear)).first());
var baselineForest = baseline.select('ndvi').gt(0.55)
  .and(baseline.select('nbr').gt(0.15))
  .rename('baseline_forest');

// Additional sensors are kept as independent context layers, not mixed into
// the 30 m optical classification because their resolution/radiometry differs.
var sentinel1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(bufferOuter)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));

var modisTerra = ee.ImageCollection('MODIS/061/MOD09A1').filterBounds(bufferOuter);
var modisAqua = ee.ImageCollection('MODIS/061/MYD09A1').filterBounds(bufferOuter);
var aster = ee.ImageCollection('ASTER/AST_L1T_003').filterBounds(bufferOuter);

function modisNdvi(collection, year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var images = collection.filterDate(start, end).map(function (image) {
    var state = image.select('StateQA');
    var cloudState = state.bitwiseAnd(3);
    var cloudShadow = state.rightShift(2).bitwiseAnd(1);
    var clear = cloudState.eq(0).and(cloudShadow.eq(0));
    var red = image.select('sur_refl_b01').multiply(0.0001);
    var nir = image.select('sur_refl_b02').multiply(0.0001);
    return nir.subtract(red).divide(nir.add(red))
      .rename('ndvi')
      .updateMask(clear);
  });
  var empty = ee.Image.constant(0).rename('ndvi')
    .updateMask(ee.Image.constant(0));
  return ee.Image(ee.Algorithms.If(images.size().gt(0), images.median(), empty))
    .clip(bufferOuter);
}

function yearChange(year) {
  year = ee.Number(year);
  var current = ee.Image(annual.filter(ee.Filter.eq('year', year)).first());
  var previous = ee.Image(annual.filter(ee.Filter.eq('year', year.subtract(1))).first());
  var transition = previous.select('ndvi').gt(0.55)
    .and(previous.select('nbr').gt(0.15))
    .and(current.select('ndvi').lt(0.35))
    .and(current.select('bsi').gt(0.05))
    .and(current.select('mndwi').lt(0.1))
    .and(baselineForest);
  var candidate = ee.Image(ee.Algorithms.If(
    year.eq(CONFIG.firstYear),
    ee.Image.constant(0).rename('candidate').clip(bufferOuter),
    transition.rename('candidate').unmask(0)
  ));
  return candidate
    .addBands(current.select('observations'))
    .set('year', year);
}

var changeImages = ee.ImageCollection.fromImages(
  ee.List.sequence(CONFIG.firstYear, CONFIG.lastYear).map(yearChange)
);

function makeAnnualRows(year) {
  year = ee.Number(year);
  var image = ee.Image(changeImages.filter(ee.Filter.eq('year', year)).first());
  var area = image.select('candidate').multiply(ee.Image.pixelArea())
    .rename('candidate_area_m2');
  var observed = image.select('observations');
  var rows = ee.FeatureCollection(zones.map(function (zone) {
    zone = ee.Feature(zone);
    var activeSites = hasMiningInventory
      ? miningSites
        .filter(ee.Filter.lte('start_year', year))
        .filter(ee.Filter.gte('end_year', year))
      : ee.FeatureCollection([]);
    var stats = area.addBands(observed).reduceRegion({
      reducer: ee.Reducer.sum().combine({
        reducer2: ee.Reducer.mean(),
        sharedInputs: false
      }),
      geometry: zone.geometry(),
      scale: CONFIG.analysisScaleMeters,
      crs: CONFIG.targetCrs,
      maxPixels: 1e10,
      tileScale: 4
    });
    var candidateArea = ee.Number(ee.Algorithms.If(
      ee.Algorithms.IsEqual(stats.get('candidate_area_m2_sum'), null),
      0,
      stats.get('candidate_area_m2_sum')
    ));
    var hansenYear = year.subtract(2000);
    var hansenLossArea = ee.Image.pixelArea()
      .updateMask(HANSEN_GFC.select('treecover2000').gte(30))
      .updateMask(HANSEN_GFC.select('lossyear').eq(hansenYear))
      .rename('hansen_loss_m2');
    var hansenStats = hansenLossArea.reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: zone.geometry(),
      scale: CONFIG.analysisScaleMeters,
      crs: CONFIG.targetCrs,
      maxPixels: 1e10,
      tileScale: 4
    });
    var hansenLossHectares = ee.Algorithms.If(
      year.gte(2001).and(year.lte(2024)),
      ee.Number(ee.Algorithms.If(
        ee.Algorithms.IsEqual(hansenStats.get('hansen_loss_m2'), null),
        0,
        hansenStats.get('hansen_loss_m2')
      )).divide(10000),
      null
    );
    var properties = ee.Dictionary({
      year: year,
      zone: zone.get('zone'),
      candidate_forest_loss_ha: ee.Algorithms.If(
        year.gt(CONFIG.firstYear).and(ee.Number(image.get('scene_count')).gt(0)),
        candidateArea.divide(10000),
        null
      ),
      gfw_hansen_v1_12_loss_ha: hansenLossHectares,
      mean_optical_observations: stats.get('observations_mean'),
      optical_scene_count: image.get('scene_count'),
      status: ee.Algorithms.If(
        ee.Number(image.get('scene_count')).eq(0),
        'Aucune_image_disponible',
        ee.Algorithms.If(year.eq(2026), 'Provisoire_annee_partielle', 'A_verifier')
      )
    });
    if (hasMiningInventory) {
      var activeInfluence = activeSites.geometry(1)
        .buffer(CONFIG.mineProximityMeters, 1)
        .intersection(bufferOuter, 1);
      var miningMask = ee.Image.constant(1).clip(activeInfluence);
      var mineStats = area.updateMask(miningMask).reduceRegion({
        reducer: ee.Reducer.sum(),
        geometry: zone.geometry(),
        scale: CONFIG.analysisScaleMeters,
        crs: CONFIG.targetCrs,
        maxPixels: 1e10,
        tileScale: 4
      });
      var mineHectares = ee.Number(ee.Algorithms.If(
        ee.Algorithms.IsEqual(mineStats.get('candidate_area_m2'), null),
        0,
        mineStats.get('candidate_area_m2')
      )).divide(10000);
      properties = properties.set('candidate_loss_within_500m_mines_ha', mineHectares)
        .set('active_mining_site_count', activeSites.size())
        .set('mining_inventory_status', ee.Algorithms.If(
          activeSites.size().gt(0),
          'Sites_actifs_selon_inventaire',
          'Aucun_site_actif_ou_dates_absentes'
        ));
    }
    return ee.Feature(null, properties);
  }));
  return rows;
}

var annualResults = ee.FeatureCollection(
  ee.List.sequence(CONFIG.firstYear, CONFIG.lastYear).map(makeAnnualRows)
).flatten();

var map = ui.Map();
map.centerObject(reserveFeatures, 8);
var panel = ui.Panel({style: {width: '360px', padding: '14px'}});
panel.add(ui.Label('Réserve de faune à okapis · mines et forêts', {
  fontSize: '18px', fontWeight: 'bold', color: '#173b31'
}));
panel.add(ui.Label(
  'Écran de détection de transitions forêt → sol nu. Les signaux doivent être vérifiés sur les images et ne constituent pas une preuve d’activité minière.',
  {whiteSpace: 'normal', color: '#56665b'}
));

var yearLabel = ui.Label('Année : 2000');
var yearSlider = ui.Slider({
  min: CONFIG.firstYear,
  max: CONFIG.lastYear,
  value: CONFIG.firstYear,
  step: 1,
  style: {stretch: 'horizontal'}
});
var layerSelect = ui.Select({
  items: ['Perte candidate', 'Perte annuelle GFW/Hansen (2001–2024)', 'NDVI optique', 'Sentinel-1 VV', 'Sentinel-1 VH', 'ASTER VNIR (scène)', 'MODIS Terra NDVI', 'MODIS Aqua NDVI'],
  value: 'Perte candidate',
  style: {stretch: 'horizontal'}
});
var summary = ui.Label('Chargement des couches…', {whiteSpace: 'normal'});
panel.add(yearLabel);
panel.add(yearSlider);
panel.add(ui.Label('Couche à afficher', {fontWeight: 'bold', margin: '10px 0 4px'}));
panel.add(layerSelect);
panel.add(summary);
panel.add(ui.Label(
  'ASTER L1T (15–90 m) est affiché en radiance numérique pour inspection seulement, jamais fusionné aux indices de réflectance. MODIS Terra/Aqua (500 m) est un contexte régional ; les catalogues peuvent présenter un retard de disponibilité.',
  {whiteSpace: 'normal', color: '#68776e', margin: '12px 0'}
));
panel.add(ui.Label(
  hasMiningInventory
    ? 'Inventaire minier chargé : renseigner start_year et end_year numériques pour filtrer les sites actifs par année.'
    : 'Aucun inventaire minier vérifié chargé : les résultats restent des changements candidats et ne sont pas attribués à des mines.',
  {whiteSpace: 'normal', color: '#795d2a', fontWeight: 'bold'}
));

function updateMap() {
  var year = Number(yearSlider.getValue());
  var composite = ee.Image(annual.filter(ee.Filter.eq('year', year)).first());
  var change = ee.Image(changeImages.filter(ee.Filter.eq('year', year)).first());
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var s1Collection = sentinel1.filterDate(start, end);
  var emptyRadar = ee.Image.constant([0, 0]).rename(['VV', 'VH'])
    .updateMask(ee.Image.constant(0));
  var s1 = ee.Image(ee.Algorithms.If(
    s1Collection.size().gt(0),
    s1Collection.median(),
    emptyRadar
  ));
  var modisT = modisNdvi(modisTerra, year);
  var modisA = modisNdvi(modisAqua, year);
  var asterYear = aster.filterDate(start, end)
    .filter(ee.Filter.listContains('ORIGINAL_BANDS_PRESENT', 'B01'))
    .filter(ee.Filter.listContains('ORIGINAL_BANDS_PRESENT', 'B02'))
    .filter(ee.Filter.listContains('ORIGINAL_BANDS_PRESENT', 'B3N'));
  var emptyAster = ee.Image.constant([0, 0, 0])
    .rename(['B3N', 'B02', 'B01'])
    .updateMask(ee.Image.constant(0));
  var asterRgb = ee.Image(ee.Algorithms.If(
    asterYear.size().gt(0),
    ee.Image(asterYear.first()).select(['B3N', 'B02', 'B01']),
    emptyAster
  ));

  yearLabel.setValue('Année : ' + year + (year === 2026 ? ' · période partielle' : ''));
  map.layers().reset();
  var selected = layerSelect.getValue();
  if (selected === 'Perte candidate') {
    map.addLayer(change.select('candidate').selfMask(),
      {min: 0, max: 1, palette: ['#dc7b35']},
      'Transition forestière candidate · ' + year);
  } else if (selected === 'Perte annuelle GFW/Hansen (2001–2024)') {
    if (year >= 2001 && year <= 2024) {
      var hansenLoss = HANSEN_GFC.select('lossyear')
        .eq(year - 2000)
        .updateMask(HANSEN_GFC.select('treecover2000').gte(30))
        .selfMask();
      map.addLayer(hansenLoss,
        {min: 1, max: 1, palette: ['#2f7893']},
        'GFW / UMD-Hansen v1.12 · perte annuelle · couvert 2000 ≥ 30 % · ' + year);
    } else {
      map.addLayer(ee.Image.constant(0).updateMask(ee.Image.constant(0)),
        {}, 'Aucune observation annuelle Hansen · ' + year);
    }
  } else if (selected === 'NDVI optique') {
    map.addLayer(composite.select('ndvi'),
      {min: -0.2, max: 0.8, palette: ['#b78252', '#e7dba4', '#9ec47d', '#276342']},
      'NDVI Landsat + Sentinel-2 · ' + year);
  } else if (selected === 'Sentinel-1 VV' || selected === 'Sentinel-1 VH') {
    var band = selected === 'Sentinel-1 VV' ? 'VV' : 'VH';
    map.addLayer(s1.select(band), {min: -25, max: 0}, selected + ' · ' + year);
  } else if (selected === 'ASTER VNIR (scène)') {
    map.addLayer(asterRgb, {min: 0, max: 255, gamma: 1.3},
      'ASTER VNIR · radiance numérique, inspection seulement · ' + year);
  } else if (selected === 'MODIS Terra NDVI') {
    map.addLayer(modisT, {min: -0.2, max: 0.8, palette: ['#b78252', '#e7dba4', '#276342']},
      'NDVI MODIS Terra · ' + year);
  } else {
    map.addLayer(modisA, {min: -0.2, max: 0.8, palette: ['#b78252', '#e7dba4', '#276342']},
      'NDVI MODIS Aqua · ' + year);
  }

  map.addLayer(ee.Image().byte().paint(reserveFeatures, 1, 2),
    {palette: ['#173b31']}, 'Limite de la réserve');
  map.addLayer(ee.Image().byte().paint(ee.FeatureCollection([
    ee.Feature(bufferOuter.difference(reserve, 1))
  ]), 1, 1), {palette: ['#b28137']}, 'Zone tampon externe de 10 km');
  if (hasMiningInventory) {
    var activeSites = miningSites
      .filter(ee.Filter.lte('start_year', year))
      .filter(ee.Filter.gte('end_year', year));
    var activeSiteBuffers = activeSites.map(function (feature) {
      return ee.Feature(feature).buffer(CONFIG.mineProximityMeters);
    });
    map.addLayer(activeSiteBuffers.style({color: '#c83f37', fillColor: 'c83f3722', width: 1}),
      {}, 'Sites miniers actifs et proximité de 500 m');
  }

  var row = ee.Feature(annualResults
    .filter(ee.Filter.eq('year', year))
    .filter(ee.Filter.eq('zone', 'Reserve')).first());
  row.toDictionary().evaluate(function (values, error) {
    if (error) {
      summary.setValue('Erreur de calcul Earth Engine : ' + error);
      return;
    }
    var hectares = values && values.candidate_forest_loss_ha;
    var scenes = ee.Number(composite.get('scene_count'));
    scenes.evaluate(function (count, countError) {
      if (countError) {
        summary.setValue('Erreur de comptage des scènes : ' + countError);
        return;
      }
      summary.setValue(
        'Réserve · ' + (hectares === null || hectares === undefined ? 'n.d.' : Number(hectares).toFixed(1) + ' ha') +
        ' de transition candidate · ' + count + ' scènes optiques filtrées.'
      );
    });
  });
}

yearSlider.onChange(updateMap);
layerSelect.onChange(updateMap);
ui.root.widgets().reset([panel, map]);
updateMap();

Export.table.toDrive({
  collection: annualResults,
  description: 'Okapi_mining_forest_change_2000_2026',
  fileNamePrefix: 'Okapi_mining_forest_change_2000_2026',
  fileFormat: 'CSV'
});

print('Années et zones à exporter', annualResults);
print('ASTER L1T scènes disponibles (radiance; inspection seulement)',
  aster.filterDate('2000-01-01', '2026-01-01').size());
print('Source de référence GFW/Hansen', 'UMD/hansen/global_forest_change_2024_v1_12; 2001–2024; canopy >= 30%');
print('Inventaire minier chargé', hasMiningInventory);

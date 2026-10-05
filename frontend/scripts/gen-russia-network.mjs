// Regenerates src/assets/russia-network.json: the dot map of Russia and the network of regional centres.
// Run outside the app's dependencies, so they stay out of package.json:
//   mkdir /tmp/geo && cd /tmp/geo && npm i world-atlas d3-geo topojson-client && node <repo>/frontend/scripts/gen-russia-network.mjs
// world-atlas: Natural Earth 1:50m (public domain), ISC. d3-geo, topojson-client: ISC.
import fs from 'fs'
import { geoConicEqualArea, geoContains } from 'd3-geo'
import { feature } from 'topojson-client'
const topo = JSON.parse(fs.readFileSync('node_modules/world-atlas/countries-50m.json'))
const countries = feature(topo, topo.objects.countries).features
const ru = countries.find(f => f.properties.name === 'Russia')
const W = 640, H = 340
const proj = geoConicEqualArea().rotate([-100, 0]).parallels([52, 68]).fitExtent([[8, 8], [W - 8, H - 8]], ru)
const crimea = ([lon, lat]) => lon > 32.4 && lon < 36.7 && lat > 44.35 && lat < 46.2
const step = 7.2
const dots = []
for (let y = step / 2; y < H; y += step) for (let x = step / 2; x < W; x += step) {
  const ll = proj.invert([x, y]); if (!ll) continue
  if (geoContains(ru, ll) || crimea(ll)) dots.push([+x.toFixed(1), +y.toFixed(1)])
}
const cities = { Москва:[37.62,55.75], 'Санкт-Петербург':[30.32,59.94], Калининград:[20.51,54.71], Мурманск:[33.08,68.97], Архангельск:[40.52,64.54], Казань:[49.11,55.79], 'Нижний Новгород':[44.0,56.33], Самара:[50.15,53.2], Ростов:[39.72,47.23], Краснодар:[38.98,45.04], Севастополь:[33.52,44.6], Уфа:[55.97,54.74], Пермь:[56.25,58.01], Екатеринбург:[60.6,56.84], Челябинск:[61.4,55.16], Тюмень:[65.53,57.15], Омск:[73.37,54.99], Новосибирск:[82.92,55.03], Томск:[84.95,56.48], Красноярск:[92.87,56.01], Иркутск:[104.28,52.29], 'Улан-Удэ':[107.6,51.83], Якутск:[129.73,62.03], Хабаровск:[135.07,48.48], Владивосток:[131.89,43.12], Магадан:[150.8,59.56], 'Петропавловск-Камчатский':[158.65,53.04], 'Южно-Сахалинск':[142.73,46.96], Норильск:[88.2,69.35], Сургут:[73.4,61.25] }
const nodes = Object.entries(cities).map(([n, ll]) => { const [x, y] = proj(ll); return { n, x: +x.toFixed(1), y: +y.toFixed(1) } })
// connections: a minimum spanning tree over the nodes, so every region is joined into one network
const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)
const inTree = [nodes.findIndex(n => n.n === 'Москва')], edges = []
while (inTree.length < nodes.length) {
  let best = null
  for (const i of inTree) nodes.forEach((b, j) => { if (inTree.includes(j)) return; const w = d(nodes[i], b); if (!best || w < best.w) best = { i, j, w } })
  inTree.push(best.j); edges.push([best.i, best.j])
}
fs.writeFileSync(process.env.OUT || 'russia-network.json', JSON.stringify({ W, H, dots, nodes, edges }))
console.log('dots', dots.length, 'nodes', nodes.length, 'edges', edges.length, 'bytes', fs.statSync(process.env.OUT || 'russia-network.json').size)

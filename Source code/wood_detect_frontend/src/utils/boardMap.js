export function coverage(rectangles) {
  const edges = [...new Set(rectangles.flatMap(r => [r.x, r.x+r.width]))].sort((a,b) => a-b)
  let total=0
  for (let i=1;i<edges.length;i++) {
    const from=edges[i-1], to=edges[i]
    const intervals=rectangles.filter(r => r.x<to && r.x+r.width>from)
      .map(r => [r.y,r.y+r.height]).sort((a,b) => a[0]-b[0])
    let end=0
    for (const [top,bottom] of intervals) {
      total+=(to-from)*Math.max(0,bottom-Math.max(top,end))
      end=Math.max(end,bottom)
    }
  }
  return Math.min(1,total)
}

export function countClasses(boxes) {
  const counts=new Map()
  for (const box of boxes) counts.set(box.category,(counts.get(box.category) || 0)+1)
  return [...counts].sort((a,b) => b[1]-a[1])
}


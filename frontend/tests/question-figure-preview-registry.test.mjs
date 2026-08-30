import assert from 'node:assert/strict'
import { createQuestionFigurePreviewRegistryCore } from '../src/utils/questionFigurePreviewRegistry.mjs'
const created=[],revoked=[],requests=[]
const urlApi={createObjectURL:(blob)=>{const url=`blob:${blob.name}`;created.push(url);return url},revokeObjectURL:(url)=>revoked.push(url)}
let resolveExisting
const registry=createQuestionFigurePreviewRegistryCore({
  http:{get:(url)=>{requests.push(url);return new Promise((resolve)=>{resolveExisting=resolve})}},urlApi,
  buildFigureUrl:(questionId,id)=>`/${questionId}/${id}`,
  createCropBlob:async(_,bbox)=>({name:`crop-${bbox.join('-')}`})
})
const existing={id:'a',kind:'existing'},crop={id:'b',kind:'crop',crop_bbox:[0,0,.2,.2]}
registry.reconcile({questionId:7,figures:[existing,crop],reachableIds:new Set(['a','b']),source:{url:'blob:source',generation:1}})
await Promise.resolve();await Promise.resolve()
assert.equal(registry.urlFor('b'),'blob:crop-0-0-0.2-0.2')
registry.reconcile({questionId:8,figures:[crop],reachableIds:new Set(['b']),source:{url:'blob:source',generation:1}})
resolveExisting({data:{name:'late'}});await Promise.resolve();await Promise.resolve()
assert.ok(revoked.includes('blob:late'))
registry.reconcile({questionId:8,figures:[],reachableIds:new Set(),source:{}})
assert.ok(revoked.includes('blob:crop-0-0-0.2-0.2'))
registry.dispose()
console.log('Question figure preview registry passed.')

// Synthetic DOM exercise of the shipped offline workflow. Never reads photos.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const template = fs.readFileSync(path.join(__dirname, '../stylematch/attribute_review.html'), 'utf8');
const data = {bundle:'synthetic-bundle', guide:'Synthetic example', vocabulary:{garment_type:['shorts','unknown'],color:['blue','unknown'],pattern:['solid','unknown']}, items:[{id:'view-001',src:'data:image/png;base64,synthetic'},{id:'view-002',src:'data:image/png;base64,synthetic'}]};
const source = template.replace('/*PAYLOAD*/null', JSON.stringify(data)).match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
function element(){return {value:'',children:[],append(x){this.children.push(x)},replaceChildren(){this.children=[]},setAttribute(){},click(){}};}
let now=0, blob;
const context={document:{hidden:false,addEventListener(){},getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},createElement:element},window:{addEventListener(){}},performance:{now:()=>now},setInterval(){},setTimeout(){},confirm:()=>true,URL:{createObjectURL(value){blob=value;return 'blob:synthetic'},revokeObjectURL(){}},Blob};
vm.createContext(context);vm.runInContext(source,context);
const read = s=>JSON.parse(vm.runInContext('JSON.stringify('+s+')',context));
assert.deepEqual(read('labels'), data.items.map(x=>({id:x.id,garment_type:'',color:'',pattern:''})));
assert.equal(elements.get('fields').children.length,3);
elements.get('next').onclick();assert.match(elements.get('progress').textContent,/Image 2 of 2/);
elements.get('prev').onclick();
elements.get('save').onclick();
(async()=>{
  let saved=JSON.parse(await blob.text());assert.equal(saved.completed_by,null);assert.equal(saved.annotation_seconds,null);
  elements.get('pause').onclick();now=2500;vm.runInContext('tick()',context);elements.get('pause').onclick();
  vm.runInContext("for(const row of labels){row.garment_type='unknown';row.color='blue';row.pattern='solid'}",context);
  elements.get('save').onclick();saved=JSON.parse(await blob.text());assert.equal(saved.completed_by,'Mark');assert.equal(saved.annotation_seconds,2.5);
  elements.get('resume').files=[{text:async()=>JSON.stringify({...saved,bundle:'wrong'})}];await elements.get('resume').onchange({target:elements.get('resume')});assert.match(elements.get('status').textContent,/Different/);
  elements.get('resume').files=[{text:async()=>JSON.stringify(saved)}];await elements.get('resume').onchange({target:elements.get('resume')});assert.match(elements.get('status').textContent,/resumed/);
  console.log('Synthetic review checks passed: blank defaults, navigation, draft/completed export, timer, same-bundle resume and wrong-bundle rejection.');
})().catch(error=>{console.error(error);process.exitCode=1});

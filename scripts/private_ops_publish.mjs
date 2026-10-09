#!/usr/bin/env node
/* Encrypted static ops publication. This is NOT server-side authentication. */
import {createCipheriv,createDecipheriv,pbkdf2Sync,randomBytes} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync,readdirSync,lstatSync,cpSync,rmSync,chmodSync} from 'node:fs';
import {basename,dirname,join,relative,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync,gunzipSync} from 'node:zlib';

const VERSION=1, ITERATIONS=600000;
const password=process.env.ONNELLAB_OPS_PASSWORD || '';
const template=join(dirname(fileURLToPath(import.meta.url)),'../templates/private_ops_unlock.html');

function requirePassword(){
 if(password.length<24 || Buffer.byteLength(password,'utf8')<24)
   throw new Error('ONNELLAB_OPS_PASSWORD must be a random 24+ character passphrase');
 if(/^(.)\1{20}/.test(password))throw new Error('Weak dashboard password');
}
function derive(salt){requirePassword();return pbkdf2Sync(Buffer.from(password,'utf8'),salt,ITERATIONS,32,'sha256');}
function encrypt(bytes,aad,key,salt){
 const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',key,iv);
 cipher.setAAD(Buffer.from(aad,'utf8'));
 const data=Buffer.concat([cipher.update(bytes),cipher.final()]);
 return {v:VERSION,it:ITERATIONS,salt:salt.toString('base64'),iv:iv.toString('base64'),
         tag:cipher.getAuthTag().toString('base64'),data:data.toString('base64'),path:aad};
}
function decrypt(blob,key){
 if(blob.v!==VERSION||blob.it!==ITERATIONS)throw new Error('Encrypted data version mismatch');
 const c=createDecipheriv('aes-256-gcm',key,Buffer.from(blob.iv,'base64'));
 c.setAAD(Buffer.from(blob.path,'utf8'));
 c.setAuthTag(Buffer.from(blob.tag,'base64'));
 return Buffer.concat([c.update(Buffer.from(blob.data,'base64')),c.final()]);
}
function traverse(root){
 let files=[];
 for(const entry of readdirSync(root,{withFileTypes:true})){
  const file=join(root,entry.name);
  if(lstatSync(file).isSymbolicLink())throw new Error('Symlink found in dashboard assets');
  if(entry.isDirectory())files.push(...traverse(file));
  else if(entry.isFile())files.push(file);
 }
 return files;
}
function jsonSafe(obj){
 return JSON.stringify(obj).replaceAll('<','\\u003c').replaceAll('&','\\u0026');
}
const [,,command,source,target]=process.argv;
if(!command||!source||!target)throw new Error('Use seal-site src dest | seal-data src dest | unseal-data src dest');
requirePassword();
if(command==='seal-site'){
 if(basename(resolve(target))!=='ops')throw new Error('Destination must be a /ops directory');
 if(resolve(source)===resolve(target))throw new Error('Source and target must differ');
 const files=traverse(source);
 if(!files.some(p=>relative(source,p)==='index.html'))throw new Error('Dashboard index missing');
 const salt=randomBytes(16),key=derive(salt),shell=readFileSync(template,'utf8');
 if(!shell.includes('__OPS_ENCRYPTED_PAYLOAD__'))throw new Error('Unlock template payload marker is missing');
 rmSync(target,{recursive:true,force:true});mkdirSync(target,{recursive:true});
 for(const file of files){
  const rel=relative(source,file).replaceAll('\\','/');
  const output=join(target,rel);mkdirSync(dirname(output),{recursive:true});
  if(rel.endsWith('.html')){
   const sealed=encrypt(gzipSync(readFileSync(file)),rel,key,salt);
   writeFileSync(output,shell.replace('__OPS_ENCRYPTED_PAYLOAD__',jsonSafe(sealed)));
  }else if(rel==='sw.js'){
   writeFileSync(output,
     "self.addEventListener('install',e=>e.waitUntil(self.skipWaiting()));\n"+
     "self.addEventListener('activate',e=>e.waitUntil((async()=>{for(const k of await caches.keys())await caches.delete(k);await self.registration.unregister()})()));\n");
  }else{cpSync(file,output);}
 }
 console.log('Encrypted static dashboard prepared');
}else if(command==='seal-data'){
 const salt=randomBytes(16),key=derive(salt),blob=encrypt(gzipSync(readFileSync(source)),'onnel-private-sales-ledger',key,salt);
 mkdirSync(dirname(target),{recursive:true});writeFileSync(target,jsonSafe(blob)+'\n');
 console.log('Encrypted private finance ledger');
}else if(command==='unseal-data'){
 const blob=JSON.parse(readFileSync(source,'utf8'));
 if(blob.path!=='onnel-private-sales-ledger')throw new Error('Unexpected encrypted data category');
 const clear=gunzipSync(decrypt(blob,derive(Buffer.from(blob.salt,'base64'))));
 mkdirSync(dirname(target),{recursive:true});writeFileSync(target,clear,{mode:0o600});
 chmodSync(target,0o600);console.log('Decrypted ledger in ephemeral workspace');
}else throw new Error('Unsupported private ops command');

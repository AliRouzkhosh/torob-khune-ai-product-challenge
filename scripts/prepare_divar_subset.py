"""Download only the Parquet ranges needed for a bounded official archive subset.
No Django, enrichment, live Divar calls, or full-archive in-memory processing.
"""
import argparse
import io
import json
from pathlib import Path
import urllib.request
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

DATASET = 'divarofficial/real_estate_ads'
URL = f'https://huggingface.co/api/datasets/{DATASET}/parquet/default/train/0.parquet'
COLUMNS = ['cat2_slug','cat3_slug','city_slug','neighborhood_slug','created_at_month','title','description',
           'credit_value','rent_value','credit_mode','rent_mode','building_size','rooms_count','floor',
           'construction_year','is_rebuilt','has_parking','has_elevator','has_warehouse','has_balcony',
           'location_latitude','location_longitude','location_radius']


class RangeFile(io.RawIOBase):
    """Small cached HTTP range reader for PyArrow's seekable Parquet input."""
    BLOCK = 2 * 1024 * 1024
    def __init__(self, url):
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
            self.url, self.size = response.url, int(response.headers['Content-Length'])
        self.position = 0
        self.cache = {}
        self.downloaded = 0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        self.position = offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if self.position < 0: raise ValueError('Negative offset')
        return self.position
    def read(self, size=-1):
        end = self.size if size<0 else min(self.size,self.position+size)
        chunks = []
        while self.position < end:
            index = self.position//self.BLOCK
            start,stop=index*self.BLOCK,min(self.size,(index+1)*self.BLOCK)-1
            if index not in self.cache:
                req=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{stop}'})
                with urllib.request.urlopen(req,timeout=45) as response:
                    expected=f'bytes {start}-{stop}/{self.size}'
                    if response.status!=206 or response.headers.get('Content-Range')!=expected:
                        raise RuntimeError('Server did not honor bounded range; no full download attempted.')
                    data=response.read(stop-start+2)
                if len(data)!=stop-start+1: raise RuntimeError('Incomplete Parquet range')
                self.cache[index]=data;self.downloaded+=len(data)
                print(f'Downloaded {self.downloaded/1048576:.1f} MiB',flush=True)
            local=self.position-start;amount=min(end-self.position,len(self.cache[index])-local)
            chunks.append(self.cache[index][local:local+amount]);self.position+=amount
        return b''.join(chunks)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='data/raw/tehran-rentals.parquet')
    parser.add_argument('--limit',type=int,default=3600)
    args=parser.parse_args()
    if not 1<=args.limit<=5000: parser.error('limit must be 1–5000')
    with urllib.request.urlopen(f'https://huggingface.co/api/datasets/{DATASET}',timeout=30) as response:
        revision=json.load(response)['sha']
    remote=RangeFile(URL)
    parquet=pq.ParquetFile(remote)
    selected=[];scanned=0;tehran=0;rentals=0
    print(f'First shard: {parquet.metadata.num_rows} rows, {parquet.num_row_groups} row groups',flush=True)
    for batch in parquet.iter_batches(batch_size=2048,columns=COLUMNS):
        city=pc.equal(batch.column('city_slug'),'tehran')
        tehran+=pc.sum(pc.cast(city,pa.int64())).as_py() or 0
        mask=pc.and_(city,pc.and_(pc.equal(batch.column('cat2_slug'),'residential-rent'),pc.equal(batch.column('cat3_slug'),'apartment-rent')))
        indices=pc.indices_nonzero(mask).to_pylist()
        rows=batch.filter(mask).to_pylist();rentals+=len(rows)
        for index,row in zip(indices,rows):
            row['source_id']=f'{revision}:train:shard0:{scanned+index}'
            selected.append(row)
            if len(selected)>=args.limit: break
        scanned+=batch.num_rows
        if len(selected)>=args.limit or scanned>=100000: break
    if not selected: raise RuntimeError('No matching rows; no output written')
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    pq.write_table(pa.Table.from_pylist(selected),destination,compression='zstd')
    manifest={'dataset':DATASET,'revision':revision,'parquet_endpoint':URL,'shard_total_rows':parquet.metadata.num_rows,
              'shard_total_bytes':remote.size,'bytes_downloaded':remote.downloaded,'raw_rows_scanned':scanned,
              'tehran_rows':tehran,'rental_apartment_rows':rentals,'selected_rows':len(selected),
              'filters':{'city_slug':'tehran','cat2_slug':'residential-rent','cat3_slug':'apartment-rent'},
              'output':str(destination.resolve())}
    destination.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__': main()

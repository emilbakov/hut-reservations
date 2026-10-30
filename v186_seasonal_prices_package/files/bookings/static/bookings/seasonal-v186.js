/* Whole-unit quotes in integer cents. Server remains authoritative. */
window.SummitDeskSeasonal={total(data,start,end){
 const first=new Date(start+'T00:00:00Z'),after=new Date(end+'T00:00:00Z');
 if(!Number.isFinite(first.getTime())||!Number.isFinite(after.getTime())||after<=first||(after-first)>3660*86400000)return 0;
 let cents=0;
 for(let day=new Date(first);day<after;day.setUTCDate(day.getUTCDate()+1)){
  const month=day.getUTCMonth()+1,key=month>=5&&month<=10?'summerPrice':'winterPrice';
  const rate=Number(data[key]??data.price??0);if(!Number.isFinite(rate)||rate<0)return 0;
  cents+=Math.round(rate*100);
 }
 return cents/100;
}};

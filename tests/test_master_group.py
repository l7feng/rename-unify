import sys,tempfile,unittest,os,csv,json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/rename-unify/code'));sys.path.insert(0,str(ROOT/'src/v4'))
import core_rules as c
from api.re_api import ReApi

class MasterGroup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def tracks(self):
        names=['誓言24_Master BUS.wav','誓言24_DX BUS.wav','誓言24_MX 2.wav']
        for n in names:(self.root/n).write_bytes(n.encode())
        return [str(self.root/n) for n in names]
    def plan(self,paths,**kw):
        return c.make_plan(paths,c.DEFAULT_TEMPLATE,c.DEFAULT_RULES,c.DEFAULT_FIELDS,root=str(self.root),date_from_mtime=False,ep_dir_template='{集数}',**kw)[0]
    def test_master_unpack_keeps_parent_and_other_groups_unchanged(self):
        items=self.plan(self.tracks(),group_master=False);master=next(i for i in items if i.target=='MIX')
        self.assertEqual(Path(master.dst).parent,self.root);self.assertNotEqual(Path(master.dst).name,Path(master.src).name)
        self.assertTrue(all('24' in Path(i.dst).parts for i in items if i.target!='MIX'))
        done,failed,log=c.apply_plan(items,log_path=str(self.root/'undo.csv'));self.assertEqual(len(done),3);self.assertFalse(failed)
        self.assertTrue(Path(master.dst).is_file());undone,errors=c.undo_from_log(log);self.assertEqual(len(undone),3);self.assertFalse(errors)
        self.assertTrue(all(Path(i.src).is_file() for i in items))
    def test_master_default_pack_and_manual_match(self):
        src=self.tracks()[0];item=self.plan([src])[0];self.assertEqual(Path(item.dst).parent,self.root/'24')
        manual=c.manual_plan_item(src,'24','MIX','Master',c.DEFAULT_TEMPLATE,c.DEFAULT_FIELDS,root=str(self.root),ep_dir_template='{集数}',group_master=False)
        self.assertEqual(Path(manual.dst).parent,self.root)
    def test_rename_files_off_keeps_unpacked_master_untouched(self):
        items=self.plan(self.tracks(),group_master=False,rename_files=False)
        master=next(i for i in items if i.target=='MIX');self.assertEqual(master.status,'skip');self.assertEqual(master.dst,master.src)
        self.assertTrue(all(i.status=='' for i in items if i.target!='MIX'))
    def test_all_final_basenames_exist_before_first_group_move(self):
        items=self.plan(self.tracks());events=[];rename=os.rename
        def traced(src,dst):events.append(('rename',str(src),str(dst)));return rename(src,dst)
        def progress(message):
            events.append(('phase',message))
            if message.startswith('阶段2'):
                self.assertFalse((self.root/'24').exists())
                staged=[p for p in self.root.glob('.ru_stage_*/*') if p.suffix=='.wav']
                self.assertEqual(sorted(p.name for p in staged),sorted(Path(i.dst).name for i in items))
        with patch.object(c.os,'rename',side_effect=traced):done,failed,_=c.apply_plan(items,write_log=False,progress=progress)
        self.assertFalse(failed);self.assertEqual(len(done),3)
        phase2=next(n for n,x in enumerate(events) if x[0]=='phase' and x[1].startswith('阶段2'))
        self.assertEqual(sum(x[0]=='rename' for x in events[:phase2]),3);self.assertEqual(sum(x[0]=='rename' for x in events[phase2:]),3)
        self.assertFalse(list(self.root.glob('.ru_stage_*')))
    def simple_items(self):
        (self.root/'a.wav').write_bytes(b'A');(self.root/'b.wav').write_bytes(b'B')
        return [c.PlanItem(str(self.root/'a.wav'),str(self.root/'1'/'same.wav')),c.PlanItem(str(self.root/'b.wav'),str(self.root/'2'/'same.wav'))]
    def test_equal_final_basenames_in_different_groups(self):
        items=self.simple_items();done,failed,_=c.apply_plan(items,write_log=False)
        self.assertEqual(len(done),2);self.assertFalse(failed);self.assertEqual((self.root/'1/same.wav').read_bytes(),b'A');self.assertEqual((self.root/'2/same.wav').read_bytes(),b'B')
    def test_first_phase_failure_restores_all_sources(self):
        items=self.simple_items();rename=os.rename
        def fail(src,dst):
            if str(src)==items[1].src:raise PermissionError('injected rename failure')
            return rename(src,dst)
        with patch.object(c.os,'rename',side_effect=fail):done,failed,_=c.apply_plan(items,write_log=False)
        self.assertFalse(done);self.assertEqual(len(failed),2);self.assertFalse((self.root/'1').exists());self.assertEqual((self.root/'a.wav').read_bytes(),b'A');self.assertEqual((self.root/'b.wav').read_bytes(),b'B');self.assertFalse(list(self.root.glob('.ru_stage_*')))
    def test_group_failure_rolls_back_already_grouped_files(self):
        items=self.simple_items();rename=os.rename
        def fail(src,dst):
            if str(dst)==items[1].dst:raise PermissionError('injected grouping failure')
            return rename(src,dst)
        with patch.object(c.os,'rename',side_effect=fail):done,failed,_=c.apply_plan(items,write_log=False)
        self.assertFalse(done);self.assertEqual(len(failed),2);self.assertEqual((self.root/'a.wav').read_bytes(),b'A');self.assertEqual((self.root/'b.wav').read_bytes(),b'B');self.assertFalse((self.root/'1/same.wav').exists());self.assertFalse(list(self.root.glob('.ru_stage_*')))
    def test_new_external_destination_never_overwritten(self):
        items=self.simple_items()
        def progress(message):
            if message.startswith('阶段2'):(self.root/'1').mkdir();(self.root/'1/same.wav').write_bytes(b'EXTERNAL')
        done,failed,_=c.apply_plan(items,write_log=False,progress=progress)
        self.assertFalse(done);self.assertEqual(len(failed),2);self.assertEqual((self.root/'1/same.wav').read_bytes(),b'EXTERNAL');self.assertEqual((self.root/'a.wav').read_bytes(),b'A')
    def test_failed_rollback_keeps_audio_journal_and_actual_path_log(self):
        items=self.simple_items();rename=os.rename
        def fail(src,dst):
            if str(dst) in [items[1].dst,items[0].src]:raise PermissionError('injected recovery failure')
            return rename(src,dst)
        with patch.object(c.os,'rename',side_effect=fail):done,failed,log=c.apply_plan(items,log_path=str(self.root/'recovery.csv'))
        self.assertFalse(done);self.assertEqual(len(failed),2);self.assertIsNotNone(log)
        with open(log,encoding='utf-8-sig',newline='') as fh:rows=list(csv.reader(fh))
        self.assertEqual(rows[1][0],items[0].src);self.assertEqual(Path(rows[1][1]).read_bytes(),b'A');self.assertTrue((Path(rows[1][1]).parent/'recovery.json').is_file())
        undone,errors=c.undo_from_log(log);self.assertEqual(len(undone),1);self.assertFalse(errors);self.assertEqual((self.root/'a.wav').read_bytes(),b'A')
    def test_cross_names_do_not_overwrite(self):
        items=self.simple_items();items[0].dst=items[1].src;items[1].dst=items[0].src
        done,failed,_=c.apply_plan(items,write_log=False);self.assertEqual(len(done),2);self.assertFalse(failed);self.assertEqual((self.root/'a.wav').read_bytes(),b'B');self.assertEqual((self.root/'b.wav').read_bytes(),b'A')
    def test_api_failure_done_event_is_false(self):
        items=self.simple_items();events=[];api=ReApi();api._emit=lambda *args:None;api._emit_event=lambda n,v:events.append((n,v));api._run_bg=lambda job,done_msg='done':api._worker(job,done_msg)
        rename=os.rename
        def fail(src,dst):
            if str(dst)==items[1].dst:raise PermissionError('injected grouping failure')
            return rename(src,dst)
        with patch('api.re_api._re',return_value={'core':c}),patch.object(c.os,'rename',side_effect=fail):api.apply([dict(src=i.src,dst=i.dst) for i in items],str(self.root))
        self.assertFalse([v for n,v in events if n=='done'][-1]['ok']);self.assertEqual([v for n,v in events if n=='applied'][-1]['done'],0)

if __name__=='__main__':unittest.main()

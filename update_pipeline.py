import re
from pathlib import Path

path = Path("pipelines/university_pipeline.py")
content = path.read_text(encoding="utf-8")

# Let's add FactCollection import if it's missing (needed for loading)
if "from knowledge.facts import FactCollection" not in content:
    content = content.replace("from knowledge.storage.fact_repository import FactRepository",
                              "from knowledge.storage.fact_repository import FactRepository\nfrom knowledge.facts import FactCollection")

# I will rewrite the _run_program_pipeline method directly
def build_new_run_program_pipeline():
    return """    def _run_program_pipeline(
        self,
        context: PipelineContext,
        program_id: str,
        program_index: int,
        total_programs: int,
        total_stages: int,
    ) -> None:
        \"\"\"Execute stages 2–6 for a single programme, with checkpointing.\"\"\"

        program = context.program

        if program is None:
            raise RuntimeError("No program is set in the pipeline context.")

        workspace = context.workspace
        
        normalized_path = (
            workspace.facts_dir(program_id)
            / "normalized_program_facts.json"
        )
        
        # If normalization is already done, we can skip straight to final output
        if normalized_path.exists():
            print("  ✓ Found normalized facts checkpoint. Skipping extraction stages.")
            facts = self.fact_repository.load(normalized_path)
            context.normalized_facts = FactCollection(facts=facts)
            normalized_facts = context.normalized_facts
        else:
            # Stage 3: Evidence Collection
            self._print_stage(3, total_stages, self.STAGES[2])
    
            workspace.create_program(program_id)
            
            # Use metadata.json as checkpoint for evidence collection
            metadata_path = workspace.program_root(program_id) / "metadata.json"
            if metadata_path.exists():
                print("  ✓ Evidence already collected (checkpoint found)")
            else:
                collector = EvidenceCollector(
                    workspace=workspace,
                    program_id=program_id,
                )
        
                collector.process_program(program.to_dict())
                print("  ✓ Evidence collected")
    
            # Stage 4: Evidence Pack Building
            self._print_stage(4, total_stages, self.STAGES[3])
    
            program_folder = workspace.program_root(program_id)
    
            context.evidence_pack = self.evidence_pack_builder.build(
                program_folder
            )
    
            evidence_pack = context.evidence_pack
    
            if evidence_pack is None:
                raise RuntimeError("Evidence pack was not created.")
    
            page_count = len(evidence_pack.pages)
            pdf_count = len(evidence_pack.pdfs)
    
            print(f"  ✓ Evidence pack ready")
            print(f"    {page_count} pages, {pdf_count} PDFs")
    
            # Stage 5: Fact Extraction
            self._print_stage(5, total_stages, self.STAGES[4])
            
            raw_facts_path = (
                workspace.facts_dir(program_id)
                / "raw_program_facts.json"
            )
            
            if raw_facts_path.exists():
                print("  ✓ Found raw facts checkpoint.")
                facts = self.fact_repository.load(raw_facts_path)
                context.raw_facts = FactCollection(facts=facts)
                raw_facts = context.raw_facts
            else:
                extraction_client = LLMClient(
                    provider=context.llm_provider,
                    usage_tracker=context.usage_tracker,
                    stage="extraction",
                    program_id=program_id,
                )
        
                extractor = KnowledgeExtractor(
                    client=extraction_client,
                )
        
                context.raw_facts = extractor.extract(
                    evidence_pack,
                )
                raw_facts = context.raw_facts
        
                # ----------------------------------------------------------
                # PDF Fact Extraction
                # ----------------------------------------------------------
        
                pdf_facts = self._run_pdf_pipeline(
                    evidence_pack=evidence_pack,
                    context=context,
                    program_id=program_id,
                )
        
                raw_facts.facts.extend(pdf_facts)
                
                # Save after ALL facts (including PDF) are collected
                self.fact_repository.save(
                    raw_facts.facts,
                    raw_facts_path,
                )
        
                print(f"  ✓ {len(raw_facts.facts)} raw facts extracted")
    
            # Stage 6: Semantic Normalization
            self._print_stage(6, total_stages, self.STAGES[5])
    
            normalization_client = LLMClient(
                provider=context.llm_provider,
                usage_tracker=context.usage_tracker,
                stage="normalization",
                program_id=program_id,
            )
    
            chunker = NormalizationChunker()
    
            chunks = chunker.chunk(raw_facts.facts)
    
            normalizer = SemanticNormalizer(
                client=normalization_client,
            )
    
            context.normalized_facts = normalizer.normalize(chunks)
            normalized_facts = context.normalized_facts
    
            if normalized_facts is None:
                raise RuntimeError("Semantic normalization failed.")
    
            self.fact_repository.save(
                normalized_facts.facts,
                normalized_path,
            )
    
            print(f"  ✓ {len(normalized_facts.facts)} normalized facts")

        # Stage 7: Final Output
        self._print_stage(7, total_stages, self.STAGES[6])
        
        # Checkpoint final output
        output_dir = workspace.final_dir(program_id)
        if (output_dir / "programme.json").exists():
             print("  ✓ Final output already generated (checkpoint found)")
             return
             
        builder = FinalOutputBuilder(
            output_directory=output_dir,
        )

        context.final_output = builder.build(
            facts=normalized_facts.facts,
            program_id=program_id,
            program_name=program.display_name,
        )
        result = context.final_output

        if result is None:
            raise RuntimeError("Final output generation failed.")

        written = len(result.get("output_files", {}))

        print(f"  ✓ {written} output files written")"""

new_method = build_new_run_program_pipeline()

# Replace the entire _run_program_pipeline method
# We need to find the start and end of it
start_idx = content.find("    def _run_program_pipeline(")
end_idx = content.find("    def _run_pdf_pipeline(")

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_method + "\n\n" + content[end_idx:]
else:
    print("Failed to find boundaries")

path.write_text(content, encoding="utf-8")
print("Updated university_pipeline.py successfully")

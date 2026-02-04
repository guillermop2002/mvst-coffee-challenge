import { IsString, IsNumber, IsNotEmpty, IsIn, IsUrl, MaxLength, Min, Max, Matches } from 'class-validator';

export class CreateCoffeeDto {
    @IsString()
    @IsNotEmpty()
    @MaxLength(100) // Prevent extremely long names
    name: string;

    @IsString()
    @IsNotEmpty()
    @MaxLength(500) // Reasonable description length
    description: string;

    @IsString()
    @IsIn(['Arabic', 'Robusta'])
    type: string;

    @IsNumber()
    @Min(0)
    @Max(10000) // Reasonable price limit
    price: number;

    @IsString()
    @IsNotEmpty()
    @IsUrl({ protocols: ['http', 'https'], require_protocol: true }) // Only allow http/https URLs
    @MaxLength(2000) // URLs can be long but not infinite
    imageUrl: string;
}

